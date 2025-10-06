#!/usr/bin/env python3
"""
Generate non-targeting guide candidates
Produces random 23nt sequences with balanced GC content
"""
import random
import sys

def calculate_gc_content(seq):
    """Calculate GC percentage"""
    gc_count = seq.count('G') + seq.count('C')
    return (gc_count / len(seq)) * 100

def has_repeats(seq, max_repeat=4):
    """Check for simple repeats (e.g., AAAA, GGGG)"""
    for base in 'ACGT':
        if base * max_repeat in seq:
            return True
    return False

def has_dinucleotide_repeats(seq, max_repeat=4):
    """Check for dinucleotide repeats (e.g., ATATAT)"""
    for base1 in 'ACGT':
        for base2 in 'ACGT':
            dinuc = base1 + base2
            if dinuc * max_repeat in seq:
                return True
    return False

def generate_candidate(length=23, gc_min=40, gc_max=60):
    """Generate a single candidate sequence"""
    max_attempts = 1000

    for _ in range(max_attempts):
        # Generate random sequence
        seq = ''.join(random.choice('ACGT') for _ in range(length))

        # Check constraints
        gc = calculate_gc_content(seq)
        if gc < gc_min or gc > gc_max:
            continue

        if has_repeats(seq, max_repeat=4):
            continue

        if has_dinucleotide_repeats(seq, max_repeat=4):
            continue

        return seq

    return None

def main():
    num_candidates = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    print(f"Generating {num_candidates} candidate sequences...")

    random.seed(42)  # For reproducibility
    candidates = []

    attempts = 0
    max_total_attempts = num_candidates * 100

    while len(candidates) < num_candidates and attempts < max_total_attempts:
        attempts += 1
        seq = generate_candidate()

        if seq and seq not in candidates:
            candidates.append(seq)

    if len(candidates) < num_candidates:
        print(f"Warning: Only generated {len(candidates)} candidates", file=sys.stderr)

    # Print candidates
    for seq in candidates:
        gc = calculate_gc_content(seq)
        print(f"{seq}\t# GC={gc:.1f}%")

    print(f"\nGenerated {len(candidates)} unique candidates", file=sys.stderr)

if __name__ == '__main__':
    main()
