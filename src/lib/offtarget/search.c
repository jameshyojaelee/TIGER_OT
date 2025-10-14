/*
 * High-performance off-target search using AVX2 + OpenMP
 *
 * Usage: offtarget_search guides.csv reference.fasta output.csv
 *
 * The guides.csv file must contain a header row with at least the columns:
 *   Gene,Sequence
 *
 * Results are written in the same order as input with columns:
 *   Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5,MM0_Transcripts,MM0_Genes
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
    size_t *mm0_transcripts;
    size_t mm0_count;
} GuideResult;

typedef struct {
    size_t start;
    size_t length;
    char *transcript_id;
    char *gene_symbol;
} TranscriptInfo;

typedef struct {
    size_t *data;
    size_t count;
    size_t capacity;
} HitList;

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

static char *xstrdup(const char *s) {
    if (!s) {
        return NULL;
    }
    size_t len = strlen(s);
    char *copy = (char *)xmalloc(len + 1);
    memcpy(copy, s, len + 1);
    return copy;
}

static char *trim_whitespace_inplace(char *s) {
    if (!s) {
        return s;
    }
    while (*s && isspace((unsigned char)*s)) {
        ++s;
    }
    char *end = s + strlen(s);
    while (end > s && isspace((unsigned char)*(end - 1))) {
        --end;
    }
    *end = '\0';
    return s;
}

static void parse_fasta_header(const char *line, char **transcript_id_out, char **gene_symbol_out) {
    char *buffer = xstrdup(line[0] == '>' ? line + 1 : line);
    size_t len = strlen(buffer);
    while (len > 0 && (buffer[len - 1] == '\n' || buffer[len - 1] == '\r')) {
        buffer[--len] = '\0';
    }

    char *saveptr = NULL;
    char *token = strtok_r(buffer, "|", &saveptr);
    char *transcript_id = NULL;
    char *gene_symbol = NULL;
    int index = 0;

    while (token) {
        char *clean = trim_whitespace_inplace(token);
        if (index == 0 && !transcript_id) {
            transcript_id = xstrdup(clean);
        } else if (index == 5 && !gene_symbol) {
            gene_symbol = xstrdup(clean);
        }
        token = strtok_r(NULL, "|", &saveptr);
        ++index;
    }

    if (!transcript_id) {
        transcript_id = xstrdup("UNKNOWN");
    }
    if (!gene_symbol) {
        gene_symbol = xstrdup("Unknown");
    }

    *transcript_id_out = transcript_id;
    *gene_symbol_out = gene_symbol;

    free(buffer);
}

static void hitlist_init(HitList *list) {
    list->data = NULL;
    list->count = 0;
    list->capacity = 0;
}

static void hitlist_free(HitList *list) {
    free(list->data);
    list->data = NULL;
    list->count = 0;
    list->capacity = 0;
}

static void hitlist_add(HitList *list, size_t value) {
    for (size_t i = 0; i < list->count; ++i) {
        if (list->data[i] == value) {
            return;
        }
    }

    if (list->count == list->capacity) {
        size_t new_capacity = list->capacity ? list->capacity * 2 : 8;
        size_t *new_data = (size_t *)realloc(list->data, new_capacity * sizeof(size_t));
        if (!new_data) {
            fprintf(stderr, "Error: realloc failed while growing hit list\n");
            free(list->data);
            exit(EXIT_FAILURE);
        }
        list->data = new_data;
        list->capacity = new_capacity;
    }

    list->data[list->count++] = value;
}

static void free_transcript_info(TranscriptInfo *transcripts, size_t count) {
    if (!transcripts) {
        return;
    }
    for (size_t i = 0; i < count; ++i) {
        free(transcripts[i].transcript_id);
        free(transcripts[i].gene_symbol);
    }
    free(transcripts);
}

static void free_results(GuideResult *results, size_t count) {
    if (!results) {
        return;
    }
    for (size_t i = 0; i < count; ++i) {
        free(results[i].mm0_transcripts);
        results[i].mm0_transcripts = NULL;
        results[i].mm0_count = 0;
    }
    free(results);
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

static Buffer load_reference_sequence(const char *filename, TranscriptInfo **transcripts_out, size_t *transcript_count_out) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "Error: unable to open reference file '%s': %s\n", filename, strerror(errno));
        exit(EXIT_FAILURE);
    }

    Buffer buffer;
    buffer_init(&buffer, 1024 * 1024);

    size_t capacity = 1024;
    TranscriptInfo *transcripts = (TranscriptInfo *)xmalloc(capacity * sizeof(TranscriptInfo));
    size_t transcript_count = 0;
    TranscriptInfo *current = NULL;

    char *line = NULL;
    size_t linecap = 0;
    ssize_t linelen;
    bool first_sequence = true;

    while ((linelen = getline(&line, &linecap, fp)) != -1) {
        if (linelen <= 1) {
            continue;
        }

        if (line[0] == '>') {
            if (!first_sequence && current) {
                current->length = buffer.length - current->start;
                append_sentinel(&buffer);
            }
            first_sequence = false;

            if (transcript_count == capacity) {
                capacity *= 2;
                TranscriptInfo *tmp = (TranscriptInfo *)realloc(transcripts, capacity * sizeof(TranscriptInfo));
                if (!tmp) {
                    fprintf(stderr, "Error: realloc failed while growing transcript metadata\n");
                    free(transcripts);
                    exit(EXIT_FAILURE);
                }
                transcripts = tmp;
            }

            char *transcript_id = NULL;
            char *gene_symbol = NULL;
            parse_fasta_header(line, &transcript_id, &gene_symbol);

            current = &transcripts[transcript_count++];
            current->start = buffer.length;
            current->length = 0;
            current->transcript_id = transcript_id;
            current->gene_symbol = gene_symbol;
            continue;
        }

        if (!current) {
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

    if (transcript_count == 0 || !current) {
        fprintf(stderr, "Error: reference '%s' contains no sequence records\n", filename);
        free(buffer.data);
        free_transcript_info(transcripts, transcript_count);
        exit(EXIT_FAILURE);
    }

    current->length = buffer.length - current->start;

    if (buffer.length == 0) {
        fprintf(stderr, "Error: reference '%s' contains no sequence data\n", filename);
        free(buffer.data);
        free_transcript_info(transcripts, transcript_count);
        exit(EXIT_FAILURE);
    }

    append_sentinel(&buffer);  // padding to allow vector loads at the end
    *transcripts_out = transcripts;
    *transcript_count_out = transcript_count;
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
    GuideResult *results,
    const TranscriptInfo *transcripts,
    size_t transcript_count
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
    HitList mm0_hits[GROUP_SIZE];
    for (size_t j = 0; j < group_size; ++j) {
        hitlist_init(&mm0_hits[j]);
    }

    size_t transcript_idx = 0;
    size_t next_boundary = (transcript_count > 1) ? transcripts[1].start : search_limit;

    for (size_t pos = 0; pos < search_limit; ++pos) {
        while (transcript_idx + 1 < transcript_count && pos >= next_boundary) {
            ++transcript_idx;
            next_boundary = (transcript_idx + 1 < transcript_count)
                ? transcripts[transcript_idx + 1].start
                : search_limit;
        }

        if (!valid_pos[pos]) {
            continue;
        }

        const TranscriptInfo *tinfo = &transcripts[transcript_idx];
        if (pos < tinfo->start) {
            continue;
        }
        size_t transcript_end = tinfo->start + tinfo->length;
        if (pos >= transcript_end) {
            continue;
        }

        __m256i ref_vec = _mm256_loadu_si256((const __m256i *)(ref_seq + pos));

        for (size_t j = 0; j < group_size; ++j) {
            if (pos + (size_t)query_lengths[j] > transcript_end) {
                continue;
            }

            __m256i cmp = _mm256_cmpeq_epi8(ref_vec, query_vec[j]);
            uint32_t eq_mask = (uint32_t)_mm256_movemask_epi8(cmp);
            eq_mask &= query_masks[j];

            int matches = __builtin_popcount(eq_mask);
            int mismatches = query_lengths[j] - matches;

            if (mismatches <= MAX_MISMATCHES) {
                local_counts[j][mismatches]++;
                if (mismatches == 0) {
                    hitlist_add(&mm0_hits[j], transcript_idx);
                }
            }
        }
    }

    for (size_t j = 0; j < group_size; ++j) {
        GuideResult *res = &results[group_start + j];
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            res->counts[mm] = local_counts[j][mm];
        }

        if (mm0_hits[j].count > 0) {
            res->mm0_transcripts = (size_t *)xmalloc(mm0_hits[j].count * sizeof(size_t));
            memcpy(res->mm0_transcripts, mm0_hits[j].data, mm0_hits[j].count * sizeof(size_t));
            res->mm0_count = mm0_hits[j].count;
        } else {
            res->mm0_transcripts = NULL;
            res->mm0_count = 0;
        }

        hitlist_free(&mm0_hits[j]);
    }
}

static void process_group_scalar(
    const char *ref_seq,
    const unsigned char *valid_pos,
    size_t search_limit,
    const Guide *guides,
    size_t group_start,
    size_t group_size,
    GuideResult *results,
    const TranscriptInfo *transcripts,
    size_t transcript_count
) {
    uint64_t local_counts[GROUP_SIZE][MAX_MISMATCHES + 1] = {{0}};
    HitList mm0_hits[GROUP_SIZE];
    for (size_t j = 0; j < group_size; ++j) {
        hitlist_init(&mm0_hits[j]);
    }

    size_t transcript_idx = 0;
    size_t next_boundary = (transcript_count > 1) ? transcripts[1].start : search_limit;

    for (size_t pos = 0; pos < search_limit; ++pos) {
        while (transcript_idx + 1 < transcript_count && pos >= next_boundary) {
            ++transcript_idx;
            next_boundary = (transcript_idx + 1 < transcript_count)
                ? transcripts[transcript_idx + 1].start
                : search_limit;
        }

        if (!valid_pos[pos]) {
            continue;
        }

        const TranscriptInfo *tinfo = &transcripts[transcript_idx];
        if (pos < tinfo->start) {
            continue;
        }
        size_t transcript_end = tinfo->start + tinfo->length;
        if (pos >= transcript_end) {
            continue;
        }

        for (size_t j = 0; j < group_size; ++j) {
            const Guide *g = &guides[group_start + j];
            if (pos + (size_t)g->length > transcript_end) {
                continue;
            }

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
                if (mismatches == 0) {
                    hitlist_add(&mm0_hits[j], transcript_idx);
                }
            }
        }
    }

    for (size_t j = 0; j < group_size; ++j) {
        GuideResult *res = &results[group_start + j];
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            res->counts[mm] = local_counts[j][mm];
        }

        if (mm0_hits[j].count > 0) {
            res->mm0_transcripts = (size_t *)xmalloc(mm0_hits[j].count * sizeof(size_t));
            memcpy(res->mm0_transcripts, mm0_hits[j].data, mm0_hits[j].count * sizeof(size_t));
            res->mm0_count = mm0_hits[j].count;
        } else {
            res->mm0_transcripts = NULL;
            res->mm0_count = 0;
        }

        hitlist_free(&mm0_hits[j]);
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

    TranscriptInfo *transcripts = NULL;
    size_t transcript_count = 0;
    Buffer reference = load_reference_sequence(reference_file, &transcripts, &transcript_count);
    if (max_guide_len > MAX_GUIDE_LEN) {
        max_guide_len = MAX_GUIDE_LEN;
    }
    unsigned char *valid_positions = compute_valid_positions(reference.data, reference.length, max_guide_len);

    size_t search_limit = 0;
    if (reference.length >= PAD_WIDTH) {
        search_limit = reference.length - (PAD_WIDTH - 1);
    }

    GuideResult *results = (GuideResult *)xmalloc((size_t)n_guides * sizeof(GuideResult));
    memset(results, 0, (size_t)n_guides * sizeof(GuideResult));

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

        if (use_avx2) {
            process_group_avx2(reference.data, valid_positions, search_limit,
                               guides, start, group_size, results,
                               transcripts, transcript_count);
        } else {
            process_group_scalar(reference.data, valid_positions, search_limit,
                                 guides, start, group_size, results,
                                 transcripts, transcript_count);
        }
    }

    FILE *out = fopen(output_file, "w");
    if (!out) {
        fprintf(stderr, "Error: unable to open output file '%s': %s\n", output_file, strerror(errno));
        free(valid_positions);
        free(reference.data);
        free(guides);
        free_results(results, (size_t)n_guides);
        free_transcript_info(transcripts, transcript_count);
        return EXIT_FAILURE;
    }

    fprintf(out, "Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5,MM0_Transcripts,MM0_Genes\n");
    for (int i = 0; i < n_guides; ++i) {
        GuideResult *res = &results[i];
        fprintf(out, "%s,%s", guides[i].gene, guides[i].sequence);
        for (int mm = 0; mm <= MAX_MISMATCHES; ++mm) {
            fprintf(out, ",%llu", (unsigned long long)res->counts[mm]);
        }

        fputc(',', out);
        if (res->mm0_count > 0) {
            size_t printed = 0;
            for (size_t idx = 0; idx < res->mm0_count; ++idx) {
                size_t t_idx = res->mm0_transcripts[idx];
                if (t_idx >= transcript_count) {
                    continue;
                }
                if (printed > 0) {
                    fputc('|', out);
                }
                fputs(transcripts[t_idx].transcript_id, out);
                ++printed;
            }
        }

        fputc(',', out);
        if (res->mm0_count > 0) {
            const char **gene_list = (const char **)xmalloc(res->mm0_count * sizeof(char *));
            size_t gene_count = 0;
            for (size_t idx = 0; idx < res->mm0_count; ++idx) {
                size_t t_idx = res->mm0_transcripts[idx];
                if (t_idx >= transcript_count) {
                    continue;
                }
                const char *gene = transcripts[t_idx].gene_symbol ? transcripts[t_idx].gene_symbol : "Unknown";
                bool seen = false;
                for (size_t g = 0; g < gene_count; ++g) {
                    if (strcmp(gene_list[g], gene) == 0) {
                        seen = true;
                        break;
                    }
                }
                if (!seen) {
                    gene_list[gene_count++] = gene;
                }
            }
            for (size_t g = 0; g < gene_count; ++g) {
                if (g > 0) {
                    fputc('|', out);
                }
                fputs(gene_list[g], out);
            }
            free((void *)gene_list);
        }

        fputc('\n', out);
    }

    fclose(out);
    free(valid_positions);
    free(reference.data);
    free(guides);
    free_results(results, (size_t)n_guides);
    free_transcript_info(transcripts, transcript_count);
    return EXIT_SUCCESS;
}
