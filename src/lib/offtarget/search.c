/*
 * High-performance off-target search using AVX2 + OpenMP
 *
 * Usage: offtarget_search guides.csv reference.fasta output.csv
 *
 * The guides.csv file must contain a header row with at least the columns:
 *   Gene,Sequence
 *
 * Results are written in the same order as input with columns:
 *   Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <immintrin.h>
#include <sys/types.h>

#ifdef _OPENMP
#include <omp.h>
#else
static inline void omp_set_num_threads(int n) { (void)n; }
static inline int omp_get_max_threads(void) { return 1; }
#endif

#define PAD_WIDTH 32
#define MAX_GUIDE_LEN 30
#define MAX_MISMATCHES 5
#define GROUP_SIZE 4
#define SENTINEL_CHAR 'X'

typedef struct {
    char gene[256];
    char sequence[MAX_GUIDE_LEN + 1];
    int length;
} Guide;

typedef struct {
    uint64_t counts[MAX_MISMATCHES + 1];
} GuideResult;

typedef struct {
    char *data;
    size_t length;
    size_t capacity;
} Buffer;

static void *xmalloc(size_t size) {
    void *ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "Error: out of memory (requested %zu bytes)\n", size);
        exit(EXIT_FAILURE);
    }
    return ptr;
}

static void buffer_init(Buffer *buf, size_t initial_capacity) {
    buf->data = (char *)xmalloc(initial_capacity);
    buf->length = 0;
    buf->capacity = initial_capacity;
}

static void buffer_reserve(Buffer *buf, size_t additional) {
    size_t required = buf->length + additional;
    if (required > buf->capacity) {
        size_t new_capacity = buf->capacity * 2;
        if (new_capacity < required) {
            new_capacity = required + 1024;
        }
        char *new_data = (char *)realloc(buf->data, new_capacity);
        if (!new_data) {
            fprintf(stderr, "Error: realloc failed while growing buffer to %zu bytes\n", new_capacity);
            free(buf->data);
            exit(EXIT_FAILURE);
        }
        buf->data = new_data;
        buf->capacity = new_capacity;
    }
}

static void buffer_append_char(Buffer *buf, char c) {
    buffer_reserve(buf, 1);
    buf->data[buf->length++] = c;
}

static void append_sentinel(Buffer *buf) {
    buffer_reserve(buf, PAD_WIDTH);
    for (int i = 0; i < PAD_WIDTH; ++i) {
        buf->data[buf->length++] = SENTINEL_CHAR;
    }
}

static inline char normalize_base(char c) {
    switch (c) {
        case 'A': case 'a': return 'A';
        case 'C': case 'c': return 'C';
        case 'G': case 'g': return 'G';
        case 'T': case 't': case 'U': case 'u': return 'T';
        default: return 'N';
    }
}

static int parse_thread_override(void) {
    const char *env = getenv("TIGER_OFFTARGET_THREADS");
    if (!env || !*env) {
        return 0;
    }
    char *endptr = NULL;
    long value = strtol(env, &endptr, 10);
    if (endptr == env || value <= 0) {
        fprintf(stderr, "Warning: ignoring invalid TIGER_OFFTARGET_THREADS value '%s'\n", env);
        return 0;
    }
    if (value > 1024) {
        value = 1024;
    }
    return (int)value;
}

static unsigned char *compute_valid_positions(const char *sequence, size_t length, int max_length) {
    unsigned char *valid = (unsigned char *)xmalloc(length);
    int consecutive = 0;
    for (ssize_t idx = (ssize_t)length - 1; idx >= 0; --idx) {
        if (sequence[idx] == SENTINEL_CHAR) {
            consecutive = 0;
            valid[idx] = 0;
        } else {
            consecutive++;
            valid[idx] = (unsigned char)(consecutive >= max_length);
        }
    }
    return valid;
}

static int load_guides(const char *filename, Guide **guides_out, int *max_len_out) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "Error: unable to open guides file '%s': %s\n", filename, strerror(errno));
        return -1;
    }

    size_t capacity = 1024;
    Guide *guides = (Guide *)xmalloc(capacity * sizeof(Guide));
    int max_len = 0;
    int count = 0;

    char *line = NULL;
    size_t linecap = 0;

    ssize_t linelen = getline(&line, &linecap, fp);  // skip header
    if (linelen < 0) {
        fprintf(stderr, "Error: guides file '%s' is empty\n", filename);
        free(line);
        free(guides);
        fclose(fp);
        return -1;
    }

    while ((linelen = getline(&line, &linecap, fp)) != -1) {
        if (linelen <= 1) {
            continue;
        }

        // Tokenize: expect Gene,Sequence,...
        char *cursor = line;
        char *gene = strsep(&cursor, ",");
        char *sequence = strsep(&cursor, ",");

        if (!gene || !sequence) {
            continue;
        }

        while (*gene && isspace((unsigned char)*gene)) {
            gene++;
        }
        while (*sequence && isspace((unsigned char)*sequence)) {
            sequence++;
        }

        char *gene_end = gene + strlen(gene);
        while (gene_end > gene && isspace((unsigned char)gene_end[-1])) {
            --gene_end;
        }
        *gene_end = '\0';

        char *seq_end = sequence + strcspn(sequence, ",\r\n");
        *seq_end = '\0';

        int len = (int)strlen(sequence);
        if (len <= 0) {
            continue;
        }
        if (len > MAX_GUIDE_LEN) {
            fprintf(stderr, "Error: guide '%s' exceeds supported length (%d > %d)\n",
                    gene, len, MAX_GUIDE_LEN);
            free(line);
            free(guides);
            fclose(fp);
            return -1;
        }

        if (count == (int)capacity) {
            capacity *= 2;
            Guide *tmp = (Guide *)realloc(guides, capacity * sizeof(Guide));
            if (!tmp) {
                fprintf(stderr, "Error: failed to grow guide buffer\n");
                free(line);
                free(guides);
                fclose(fp);
                return -1;
            }
            guides = tmp;
        }

        Guide *g = &guides[count];
        strncpy(g->gene, gene, sizeof(g->gene) - 1);
        g->gene[sizeof(g->gene) - 1] = '\0';
        for (int i = 0; i < len; ++i) {
            g->sequence[i] = normalize_base(sequence[i]);
        }
        g->sequence[len] = '\0';
        g->length = len;
        if (len > max_len) {
            max_len = len;
        }
        count++;
    }

    free(line);
    fclose(fp);

    if (count == 0) {
        fprintf(stderr, "Error: no guides found in '%s'\n", filename);
        free(guides);
        return -1;
    }

    *guides_out = guides;
    *max_len_out = max_len;
    return count;
}

static Buffer load_reference_sequence(const char *filename) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "Error: unable to open reference file '%s': %s\n", filename, strerror(errno));
        exit(EXIT_FAILURE);
    }

    Buffer buffer;
    buffer_init(&buffer, 1024 * 1024);

    char *line = NULL;
    size_t linecap = 0;
    ssize_t linelen;
    bool first_sequence = true;

    while ((linelen = getline(&line, &linecap, fp)) != -1) {
        if (linelen <= 1) {
            continue;
        }

        if (line[0] == '>') {
            if (!first_sequence) {
                append_sentinel(&buffer);
            }
            first_sequence = false;
            continue;
        }

        for (ssize_t i = 0; i < linelen; ++i) {
            char c = line[i];
            if (c == '\n' || c == '\r') {
                continue;
            }
            buffer_append_char(&buffer, normalize_base(c));
        }
    }

    free(line);
    fclose(fp);

    if (buffer.length == 0) {
        fprintf(stderr, "Error: reference '%s' contains no sequence data\n", filename);
        free(buffer.data);
        exit(EXIT_FAILURE);
    }

    append_sentinel(&buffer);  // padding to allow vector loads at the end
    return buffer;
}

static inline uint32_t mask_for_length(int length) {
    if (length >= 32) {
        return 0xFFFFFFFFu;
    }
    return (1u << length) - 1u;
}

static void process_group_avx2(
    const char *ref_seq,
    const unsigned char *valid_pos,
    size_t search_limit,
    const Guide *guides,
    size_t group_start,
    size_t group_size,
    uint64_t (*out_counts)[MAX_MISMATCHES + 1]
) {
    __m256i query_vec[GROUP_SIZE];
    uint32_t query_masks[GROUP_SIZE];
    int query_lengths[GROUP_SIZE];

    char padded[GROUP_SIZE][PAD_WIDTH];
    memset(padded, SENTINEL_CHAR, sizeof(padded));

    for (size_t j = 0; j < group_size; ++j) {
        const Guide *g = &guides[group_start + j];
        memcpy(padded[j], g->sequence, (size_t)g->length);
        query_vec[j] = _mm256_loadu_si256((const __m256i *)padded[j]);
        query_masks[j] = mask_for_length(g->length);
        query_lengths[j] = g->length;
    }

    uint64_t local_counts[GROUP_SIZE][MAX_MISMATCHES + 1] = {{0}};

    for (size_t pos = 0; pos < search_limit; ++pos) {
        if (!valid_pos[pos]) {
            continue;
        }

        __m256i ref_vec = _mm256_loadu_si256((const __m256i *)(ref_seq + pos));

        for (size_t j = 0; j < group_size; ++j) {
            __m256i cmp = _mm256_cmpeq_epi8(ref_vec, query_vec[j]);
            uint32_t eq_mask = (uint32_t)_mm256_movemask_epi8(cmp);
            eq_mask &= query_masks[j];

            int matches = __builtin_popcount(eq_mask);
            int mismatches = query_lengths[j] - matches;

            if (mismatches <= MAX_MISMATCHES) {
                local_counts[j][mismatches]++;
            }
        }
    }

    for (size_t j = 0; j < group_size; ++j) {
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            out_counts[j][mm] = local_counts[j][mm];
        }
    }
}

static void process_group_scalar(
    const char *ref_seq,
    const unsigned char *valid_pos,
    size_t search_limit,
    const Guide *guides,
    size_t group_start,
    size_t group_size,
    uint64_t (*out_counts)[MAX_MISMATCHES + 1]
) {
    uint64_t local_counts[GROUP_SIZE][MAX_MISMATCHES + 1] = {{0}};

    for (size_t pos = 0; pos < search_limit; ++pos) {
        if (!valid_pos[pos]) {
            continue;
        }

        for (size_t j = 0; j < group_size; ++j) {
            const Guide *g = &guides[group_start + j];
            int mismatches = 0;
            for (int k = 0; k < g->length; ++k) {
                if (ref_seq[pos + k] != g->sequence[k]) {
                    mismatches++;
                    if (mismatches > MAX_MISMATCHES) {
                        break;
                    }
                }
            }
            if (mismatches <= MAX_MISMATCHES) {
                local_counts[j][mismatches]++;
            }
        }
    }

    for (size_t j = 0; j < group_size; ++j) {
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            out_counts[j][mm] = local_counts[j][mm];
        }
    }
}

int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <guides.csv> <reference.fasta> <output.csv>\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *guides_file = argv[1];
    const char *reference_file = argv[2];
    const char *output_file = argv[3];

    Guide *guides = NULL;
    int max_guide_len = 0;
    int n_guides = load_guides(guides_file, &guides, &max_guide_len);
    if (n_guides <= 0) {
        return EXIT_FAILURE;
    }

    Buffer reference = load_reference_sequence(reference_file);
    if (max_guide_len > MAX_GUIDE_LEN) {
        max_guide_len = MAX_GUIDE_LEN;
    }
    unsigned char *valid_positions = compute_valid_positions(reference.data, reference.length, max_guide_len);

    size_t search_limit = 0;
    if (reference.length >= PAD_WIDTH) {
        search_limit = reference.length - (PAD_WIDTH - 1);
    }

    GuideResult *results = (GuideResult *)xmalloc((size_t)n_guides * sizeof(GuideResult));
    for (int i = 0; i < n_guides; ++i) {
        memset(results[i].counts, 0, sizeof(results[i].counts));
    }

    int requested_threads = parse_thread_override();
    if (requested_threads > 0) {
        omp_set_num_threads(requested_threads);
    }

    size_t total_groups = (n_guides + GROUP_SIZE - 1) / GROUP_SIZE;

    bool use_avx2 = true;
#if defined(__GNUC__) && defined(__x86_64__)
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "Warning: CPU does not support AVX2, falling back to scalar implementation\n");
        use_avx2 = false;
    }
#endif

#pragma omp parallel for schedule(dynamic)
    for (size_t group_idx = 0; group_idx < total_groups; ++group_idx) {
        size_t start = group_idx * GROUP_SIZE;
        size_t remaining = (size_t)n_guides - start;
        size_t group_size = remaining < GROUP_SIZE ? remaining : GROUP_SIZE;

        uint64_t local_counts[GROUP_SIZE][MAX_MISMATCHES + 1];
        memset(local_counts, 0, sizeof(local_counts));

        if (use_avx2) {
            process_group_avx2(reference.data, valid_positions, search_limit,
                               guides, start, group_size, local_counts);
        } else {
            process_group_scalar(reference.data, valid_positions, search_limit,
                                 guides, start, group_size, local_counts);
        }

        for (size_t j = 0; j < group_size; ++j) {
            GuideResult *res = &results[start + j];
            for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
                res->counts[mm] = local_counts[j][mm];
            }
        }
    }

    FILE *out = fopen(output_file, "w");
    if (!out) {
        fprintf(stderr, "Error: unable to open output file '%s': %s\n", output_file, strerror(errno));
        free(valid_positions);
        free(reference.data);
        free(guides);
        free(results);
        return EXIT_FAILURE;
    }

    fprintf(out, "Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5\n");
    for (int i = 0; i < n_guides; ++i) {
        fprintf(out, "%s,%s", guides[i].gene, guides[i].sequence);
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            fprintf(out, ",%llu", (unsigned long long)results[i].counts[mm]);
        }
        fputc('\n', out);
    }

    fclose(out);
    free(valid_positions);
    free(reference.data);
    free(guides);
    free(results);
    return EXIT_SUCCESS;
}
