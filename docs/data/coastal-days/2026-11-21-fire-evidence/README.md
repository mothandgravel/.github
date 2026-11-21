# 21 November 2026 / fire evidence

This packet supplements the original Coastal watch capture and evening source recheck. The local publication and product labels use EET (UTC+02:00). The daylight photograph's camera timezone is unknown.

## Finnish Border Guard

[Rajavartiolaitos](https://raja.fi/medialle) permits publication of its ePressi photos with credit. The two official JPEGs are reproduced byte for byte, with credit to Rajavartiolaitos / Finnish Border Guard. The close-up shows flames and smoke aboard Sparta II. The camera overlay reads `21/11/26 16:38:09:08`. The timezone and final field are unverified. The evening image shows firefighting. Its camera time is unknown.

The [named Border Guard statement](https://raja.fi/en/-/finnish-border-guard-is-leading-maritime-rescue) carries a publication label of 14:58 EET on the agency site and 15:03 EET in its ePressi copy. The [agency evening update](https://raja.fi/en/-/the-finnish-border-guard-continues-to-lead-the-rescue-operations-in-the-gulf-of-finland) carries a 20:42 EET publication label. The camera, publication, modification and retrieval timestamps have different meanings. Yle reported release of a firefighting video at 21:31 EET. A directly playable copy of the footage remains unverified. The official record JSON preserves the release, photo and report sources and their retrieval hashes.

## EUMETSAT

Four Fire Temperature RGB and two 10.5 μm infrared WMS responses were captured unchanged. All decode as opaque 1100 × 400 PNGs with distinct hashes. The selected product labels were confirmed against both provider time lists. The crop is 23–28.5° E, 59–61° N. It contains render values, with neither calibrated numeric brightness temperatures nor exact pixel times. The 17:00 EET Fire Temperature frame contains two very dark RGBA values. It is present and decodable. The six selected views provide no attribution of a thermal signal to the ship. Cloud and sampling limits leave the cause of any missing signal unresolved.

EUMETSAT Meteosat FCI image products 2026, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), under Articles 4–6 and Annex II of the [EUMETSAT data policy](https://www-cdn.eumetsat.int/files/2026-02/44253%20-%20Basic%20Documents.pdf#page=210). See the [Fire Temperature quick guide](https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide) and [10.5 μm layer description](https://view.eumetsat.int/productviewer/productDetails/mtg_fd:ir105_hrfi).

## NASA

The regional summary applies the Finnish civil-day interval [20 November 22:00 UTC, 21 November 22:00 UTC) and the same bounding rectangle to three rolling FIRMS exports saved at 22:02 EET. The capture precedes the day's end. All nine regional VIIRS detection centroids fall on Natural Earth mapped land. MODIS returned zero regional rows. These are results from the saved rolling exports. The dated FIRMS requests reached Earthdata Login. The CMR search found 15 VIIRS active-fire granules whose catalogue footprints intersect the region. Individual pixel measurements, clear-sky coverage and full-day detection completeness remain unverified. No precise detection coordinates are included.

`sha256.json` binds the exact public packet. URLs, clocks and provider response hashes are listed in the receipts and summaries. The original response bodies behind the NASA summary and issuing-agency web-page evidence are retained in the local research capture.
