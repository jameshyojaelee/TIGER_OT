# Makefile for off-target search

CC = gcc
CFLAGS = -O3 -march=native -Wall -Wextra
TARGET = ../../../bin/offtarget_search
SRC = search.c

all: $(TARGET)

$(TARGET): $(SRC)
	@mkdir -p ../../../bin
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)
	@echo "Built $(TARGET)"

clean:
	rm -f $(TARGET)

.PHONY: all clean
