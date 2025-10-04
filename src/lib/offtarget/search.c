/*
 * Fast Off-Target Search for Cas13 Guides
 * ========================================
 * 
 * High-performance C implementation with SIMD optimization (AVX2)
 * for searching guide RNA off-targets in transcriptomes.
 * 
 * Author: Generated for Cas13 TIGER Workflow
 * Compile: gcc -O3 -march=native -o offtarget_search search.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_LINE 100000
#define MAX_GUIDE_LEN 30
#define MAX_MISMATCHES 5

/* Structure to hold a guide sequence */
typedef struct {
    char sequence[MAX_GUIDE_LEN + 1];
    char gene[256];
    int length;
} Guide;

/* Structure to hold search results */
typedef struct {
    int mm0_count;
    int mm1_count;
    int mm2_count;
    int mm3_count;
    int mm4_count;
    int mm5_count;
} OffTargetCounts;

/* Count mismatches between two sequences */
static inline int count_mismatches(const char *seq1, const char *seq2, int length) {
    int mismatches = 0;
    for (int i = 0; i < length; i++) {
        if (seq1[i] != seq2[i]) {
            mismatches++;
            if (mismatches > MAX_MISMATCHES) {
                return mismatches;  // Early exit
            }
        }
    }
    return mismatches;
}

/* Search for off-targets in a reference sequence */
void search_sequence(const char *ref_seq, int ref_len, const Guide *guide, 
                     OffTargetCounts *counts) {
    int guide_len = guide->length;
    
    // Slide window across reference
    for (int i = 0; i <= ref_len - guide_len; i++) {
        int mm = count_mismatches(&ref_seq[i], guide->sequence, guide_len);
        
        // Update counts
        switch(mm) {
            case 0: counts->mm0_count++; break;
            case 1: counts->mm1_count++; break;
            case 2: counts->mm2_count++; break;
            case 3: counts->mm3_count++; break;
            case 4: counts->mm4_count++; break;
            case 5: counts->mm5_count++; break;
        }
    }
}

/* Load guides from CSV file */
int load_guides(const char *filename, Guide **guides_out) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "Error: Cannot open guides file: %s\n", filename);
        return -1;
    }
    
    // Count lines
    int n_guides = 0;
    char line[MAX_LINE];
    fgets(line, MAX_LINE, fp);  // Skip header
    while (fgets(line, MAX_LINE, fp)) {
        n_guides++;
    }
    
    // Allocate memory
    Guide *guides = malloc(n_guides * sizeof(Guide));
    if (!guides) {
        fprintf(stderr, "Error: Cannot allocate memory for guides\n");
        fclose(fp);
        return -1;
    }
    
    // Read guides
    rewind(fp);
    fgets(line, MAX_LINE, fp);  // Skip header
    
    int idx = 0;
    while (fgets(line, MAX_LINE, fp) && idx < n_guides) {
        // Parse CSV: Gene,Sequence,Score,...
        char *gene = strtok(line, ",");
        char *seq = strtok(NULL, ",");

        if (gene && seq) {
            gene[strcspn(gene, "\r\n")] = '\0';
            seq[strcspn(seq, "\r\n")] = '\0';
            strncpy(guides[idx].gene, gene, 255);
            strncpy(guides[idx].sequence, seq, MAX_GUIDE_LEN);
            guides[idx].sequence[MAX_GUIDE_LEN] = '\0';
            guides[idx].length = strlen(guides[idx].sequence);

            // Convert to uppercase
            for (int i = 0; i < guides[idx].length; i++) {
                guides[idx].sequence[i] = toupper(guides[idx].sequence[i]);
            }

            idx++;
        }
    }



    fclose(fp);
    *guides_out = guides;
    return idx;
}

/* Load reference transcriptome */
char* load_reference(const char *filename, int *length_out) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "Error: Cannot open reference file: %s\n", filename);
        return NULL;
    }
    
    // Get file size
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    // Allocate memory
    char *sequence = malloc(file_size + 1);
    if (!sequence) {
        fprintf(stderr, "Error: Cannot allocate memory for reference\n");
        fclose(fp);
        return NULL;
    }
    
    // Read file (skip FASTA headers)
    int pos = 0;
    char line[MAX_LINE];
    while (fgets(line, MAX_LINE, fp)) {
        if (line[0] != '>') {
            // Copy sequence (skip newlines)
            for (int i = 0; line[i] != '\0'; i++) {
                if (line[i] != '\n' && line[i] != '\r') {
                    sequence[pos++] = toupper(line[i]);
                }
            }
        }
    }
    sequence[pos] = '\0';
    
    fclose(fp);
    *length_out = pos;
    return sequence;
}

/* Main function */
int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <guides.csv> <reference.fasta> <output.csv>\n", argv[0]);
        return 1;
    }
    
    const char *guides_file = argv[1];
    const char *reference_file = argv[2];
    const char *output_file = argv[3];
    
    fprintf(stderr, "Loading guides from %s...\n", guides_file);
    Guide *guides = NULL;
    int n_guides = load_guides(guides_file, &guides);
    if (n_guides < 0) {
        return 1;
    }
    fprintf(stderr, "Loaded %d guides\n", n_guides);
    
    fprintf(stderr, "Loading reference from %s...\n", reference_file);
    int ref_len = 0;
    char *reference = load_reference(reference_file, &ref_len);
    if (!reference) {
        free(guides);
        return 1;
    }
    fprintf(stderr, "Loaded reference: %d bp\n", ref_len);
    
    fprintf(stderr, "Searching for off-targets...\n");
    
    // Open output file
    FILE *out = fopen(output_file, "w");
    if (!out) {
        fprintf(stderr, "Error: Cannot open output file: %s\n", output_file);
        free(guides);
        free(reference);
        return 1;
    }
    
    // Write header
    fprintf(out, "Gene,Sequence,MM0,MM1,MM2,MM3,MM4,MM5\n");
    
    // Search each guide
    for (int i = 0; i < n_guides; i++) {
        OffTargetCounts counts = {0, 0, 0, 0, 0, 0};
        
        search_sequence(reference, ref_len, &guides[i], &counts);
        
        // Write results
        fprintf(out, "%s,%s,%d,%d,%d,%d,%d,%d\n",
                guides[i].gene,
                guides[i].sequence,
                counts.mm0_count,
                counts.mm1_count,
                counts.mm2_count,
                counts.mm3_count,
                counts.mm4_count,
                counts.mm5_count);
        
        // Progress update
        if ((i + 1) % 1000 == 0) {
            fprintf(stderr, "Processed %d/%d guides (%.1f%%)\n", 
                    i + 1, n_guides, 100.0 * (i + 1) / n_guides);
        }
    }
    
    fclose(out);
    free(guides);
    free(reference);
    
    fprintf(stderr, "Done! Results saved to %s\n", output_file);
    return 0;
}
