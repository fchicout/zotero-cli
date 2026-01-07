import rispy
import sys

file_path = 'tmp/ScienceDirect_citations_1766764784932.ris'
try:
    with open(file_path, 'r', encoding='utf-8') as ris_file:
        entries = rispy.load(ris_file)
        if entries:
            print("Keys in first entry:", entries[0].keys())
            print("First entry:", entries[0])
        else:
            print("No entries found.")
except Exception as e:
    print(f"Error: {e}")
