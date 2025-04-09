import io
import re

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

bad_char = re.compile(r'[^ACGT]')

def normalise_fasta(input_text: str, output_stream):
    contig_names = []

    for record in SeqIO.parse(io.StringIO(input_text), "fasta"):
        name = record.id
        sequence = str(record.seq).upper()

        m = re.match(r'^(.+[_-])?([0-9]+(\\.[0-9]+)?)$', name)
        if m is None:
            print(f"Skipping badly formatted allele '{name}'")
            continue

        if bad_char.search(sequence):
            # Some schemes had non-ACGT characters
            continue

        if len(sequence.strip()) == 0:
            # pubmlst_neisseria_62/NEIS1690.fa.gz has an allele with
            # no content. I assume it is because it needs to be removed
            continue

        normalized_record = SeqRecord(
            Seq(sequence),
            id=m[2],
            description=""
        )
        SeqIO.write(normalized_record, output_stream, "fasta")
        contig_names.append(m[2])

    if len(contig_names) == 0:
        raise ValueError("Expected there to be some contigs")

    return contig_names
