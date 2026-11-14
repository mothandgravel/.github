# Weather passage / 11 November 2026

Saved civilian environmental context for Coastal watch. This packet contains 144 EUMETSAT cloud-product slots across the Finnish civil day, twelve Estonian precipitation composites around 10 UTC, and pointers to unchanged FMI buoy observations in the original source notebook. It is not a live feed or an incident reconstruction.

The civil-day window is 10 November 22:00 UTC inclusive to 11 November 22:00 UTC exclusive. Every original download has a SHA-256 HTTP receipt with separate request and completion times. Neither retrieval clock establishes first publication or original station reception.

## Clouds

Original WMS PNG bytes from the EUMETView `mtg_fd:rgb_geocolour` layer are unchanged. The 1,100 × 400 `CRS:84` crop covers 23–28.5° E, 59–61° N. The complete time-domain response enumerates the selected ten-minute product slots. A product timestamp is not the acquisition time of every pixel. The website adds contextual coastlines, labels and layout cropping; it does not infer cloud velocity or rainfall from RGB colours.

Contains modified EUMETSAT Meteosat product 2026. FCI Advanced Image Products are Core products under Article 4 of the [EUMETSAT Data Policy, February 2026 Basic Documents](https://www-cdn.eumetsat.int/files/2026-02/44253%20-%20Basic%20Documents.pdf#page=210). Articles 5–6 permit access and redistribution under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) with attribution. No endorsement is implied.

## Estonian radar

Original HDF5 composites from Keskkonnaagentuur's public archive are retained under [CC BY 4.0](https://keskkonnaportaal.ee/et/avaandmed/meteoroloogiliste-radarite-andmestik). The source nodes are `eesyr,eehar`: Sürgavere and Harku, combined into one derived weather product. These are not vessel-radar recordings.

The inspected quantity is `RATE`, a radar-derived rain-rate estimate in mm/h. It is not surface rain-gauge accumulation. Calibration comes from the files: gain 1, offset 0, no-data 65535, below-detection 0. The latter two codes both have unknown physical values in the inspection model; below detection is not reported as a measured zero. Dataset scan start/end timestamps and the file's product clock are retained separately.

Each 720 × 720 float32 matrix is copied unchanged in native row/column order to deterministic gzip, little endian. The browser verifies the decompressed length and SHA-256 before sampling. PNGs are derived categorical palettes without smoothing: missing cells are transparent over a hatch, below detection is blue-grey, positive estimates follow the recorded palette. Palette values above 10 mm/h share the last colour; original floats remain available.

**Georeferencing is unresolved.** With the supplied Mercator projection, the corner coordinates imply spans around 1,127,576 × 1,125,557 m, while the declared grid dimensions/scales imply around 580,003 × 558,527 m. The lower corners also have different latitudes. The website therefore shows the native grid without a geographic overlay or location-level sampling. No silent scale correction is applied. Full source projection and corner attributes are in the notebook. See the [agency's format and filtering documentation](https://keskkonnaportaal.ee/et/avaandmed/radariandmestik/radariandmete-kirjeldus).

## Buoys

The original FMI source packet supplies hourly requested samples for Gulf of Finland, Suomenlinna and Orrengrund. Values and raw `NaN` strings are unchanged. Original XML files and their earlier receipts remain in `data/coastal-sources/2026-11-11/raw/`; the source packet's first capture does not supply a download-completion timestamp, and this is not backfilled.

FMI defines direction as **from**, clockwise degrees from north; modal period is the dominant wave period. The reported directional spread is not an uncertainty confidence interval. The sinusoidal drawing is explicitly a schematic of the reported statistics, not a measured waveform or recovered spectrum. [FMI definitions](https://en.ilmatieteenlaitos.fi/guidance-to-observations); [FMI open-data licence](https://en.ilmatieteenlaitos.fi/open-data-licence).

## Rebuild and inspect

Install the pinned decoder requirements from `tools/specimens/coastal-weather-requirements.txt` into an isolated environment. Run `python scripts/build_coastal_weather.py --check` to rebuild and compare the notebook, derived matrices/images and provenance inventory entirely offline. The explicit network acquisition tool is `scripts/capture_coastal_weather.py`; it caps responses at 2 MB, checks storage, keeps TLS verification enabled, and preserves prior captures.

The cursor never chooses a future record. Cloud slots expire after ten minutes; radar requires a completed scan within five minutes and remains inside the saved strip; buoy hours select the corresponding original sample even when missing. No interpolation fills gaps. Full notebook, original bytes and individual inspection exports retain these boundaries.
