TNT measured-data extract for the Moth & Gravel maintenance evidence study

Upstream project: https://github.com/prettore/TNT
Pinned revision: e213681d00b9fd4ec8bd96da63209f017a898b65
Authors and contributors: see the upstream repository and publications.
Version of record: P. H. L. Rettore, J. Loevenich and R. R. F. Lopes,
IEEE Access (2022), DOI 10.1109/ACCESS.2022.3208283.
The repository README cites the earlier 2021 preprint, with Peter Sevenich.

The three files in source/ are unchanged CSV bytes from:
experiment_testbed/data/statistics/long/

sender.csv:
tb_sender_pckts_ManhattanGrid_VHF_1000p1to50p_20t.csv
receiver.csv:
tb_receiver_pckts_ManhattanGrid_VHF_1000p1to50p_20t.csv
summary.csv:
tb_ip_statistics_ManhattanGrid_VHF_1000p1to50p_20t.csv

Upstream declares GNU GPL version 3. The accompanying LICENSE.txt reproduces
that licence. These source data files and the derived maintenance-tnt.json
are provided under GPL-3.0 with the upstream attribution retained.

Transformation: scripts/build_maintenance_tnt.py in the site repository.
The builder verifies fixed SHA-256 hashes, preserves original CSV fields and
row numbers, and matches each flow's IPv4 identification value by chronological
occurrence. Relative times use integer microseconds. The derived summary must
match the publisher's counts and recorded delays within one microsecond.

No upstream experiment software is embedded or executed by this viewer.
No radio, operational military network or application acknowledgement is
connected. The source files contain capture-local time strings without timezone;
the source clocks were not independently calibrated for this study.

The viewer is a Moth & Gravel interpretation, with no implied affiliation,
endorsement or military equipment qualification.
