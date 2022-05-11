"""
align sequences using MAFFT
"""

from enum import Enum
from pathlib import Path
import subprocess
from typing import Optional

from latch import small_task, workflow
from latch.types import LatchFile


class AlignmentMode(Enum):
    linsi = "L-INS-i"
    fftns2 = "FFT-NS-2"
    auto = "auto"
    
@small_task
def align_sequences_task(
    unaligned_seqs: LatchFile,
    alignment_mode: AlignmentMode = AlignmentMode.auto,
    output_file_name: Optional[str] = None
    ) -> LatchFile:

    ## specify output file name
    if not output_file_name:
        out_file = Path("alignment_mafft.fa").resolve()
    else:
        out_file = output_file_name


    ## logic for how to align seqs
    if alignment_mode.value == AlignmentMode.linsi:
        _mafft_cmd = [
            "mafft-linsi",
            unaligned_seqs.local_path,
        ]
    elif alignment_mode.value == AlignmentMode.fftns2:
        _mafft_cmd = [
            "mafft",
            unaligned_seqs.local_path,
        ]
    else:  # alignment_mode.value == AlignmentMode.auto
        _mafft_cmd = [
            "mafft",
            "--auto",
            unaligned_seqs.local_path,
        ]

    with open(out_file, "w") as f:
        subprocess.call(_mafft_cmd, stdout=f)

    if not output_file_name:
        return LatchFile(str(out_file), f"latch:///{out_file.name}")
    else:
        return LatchFile(str(out_file), f"latch:///{out_file}")


@workflow
def align_sequences_mafft(
    unaligned_seqs: LatchFile,
    alignment_mode: AlignmentMode = AlignmentMode.auto,
    output_file_name: Optional[str] = None
    ) -> LatchFile:
    """
    MAFFT
    ----
    # MAFFT, the multiple sequence alignment trimming toolkit
    ## About
    MAFFT is a multiple sequence alignment program.

    <br /><br />

    If you found MAFFT useful, please cite *MAFFT Multiple Sequence Alignment
    Software Version 7: Improvements in Performance and Usability*. Katoh & Standley 2013,
    Molecular Biology and Evolution. doi:
    [10.1093/molbev/mst010](https://academic.oup.com/mbe/article/30/4/772/1073398).

    <br /><br />

    ## Modes
    Herein, we describe the various aligning modes implemented in MAFFT. If you are not sure
    which is appropriate for you, we recommend using the auto trimming mode.
    <br />
    - L-INS-i: an accurate option (L-INS-i) for an alignment of up to ∼200 sequences × ∼2,000 sites
    - FFT-NS-2: a fast option (FFT-NS-2) for a larger sequence alignment
    - auto: allow MAFFT to decide

    __metadata__:
        display_name: Align sequences using MAFFT
        author: Jacob L. Steenwyk
            name: Jacob L. Steenwyk
            email: jlsteenwyk@gmail.com
            github: https://github.com/JLSteenwyk
        repository: https://mafft.cbrc.jp/alignment/software/
        license:
            id: BSD

    Args:

        unaligned_seqs:
            Input multi-FASTA file of nucleotide or amino acid sequences 
            __metadata__:
                display_name: "Input multi-FASTA file"
                appearance:
					comment: "Input multi-FASTA file"

        alignment_mode:
            Mode for multiple sequence alignment 
            __metadata__:
                display_name: "Alignment mode (see About for details)"
                appearance:
					comment: "- auto
                    - L-INS-i
                    - FFT-NS-2"

        output_file_name:
            Name of output file that contains aligned sequences.
			__metadata__:
				display_name: "Output file"
				appearance:
					comment: "Output file in FASTA format."

    """

    return align_sequences_task(
        unaligned_seqs=unaligned_seqs,
        alignment_mode=alignment_mode,
        output_file_name=output_file_name
        )
