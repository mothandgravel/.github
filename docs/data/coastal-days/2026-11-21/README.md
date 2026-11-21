# Coastal watch / 21 November 2026

A saved public-source notebook for the Finnish civil day, starting
20 November at 22:00 UTC. Environmental requests end inclusively at
21 November 17:00 UTC (19:00 EET); the later evening was not requested.
Each response has its own request and download clocks. This is not a live feed.

- FMI: weather station 101039, wave buoys 108495 and 134221, Hamina gauge
  134254. Source station names and coordinates are checked from the XML.
  Raw `NaN` is retained as a missing value, never zero. Wave labels start
  a 1600- or 1800-second measurement series. WTP is modal period; ModalWDi
  is a from direction; WHDD is directional spread. Sea level is mm N2000;
  WATLEV is a separate mm value relative to theoretical mean sea level.
  An initial research query for station 100928 returned Kumlinge and was
  rejected by source-metadata inspection. Its research capture is retained
  locally; no values from that query are included in this packet.
- Three Orrengrund requests: 30-minute, hourly and omitted-timestep. The
  39 requested half-hour labels contain 19 numeric heights and 20 NaNs.
  Hourly sampling retains 11; the eight numeric half-past values agree
  with the omitted-timestep response. All five buoy channels are compared.
- Digitraffic: one latest-returned point for MMSI 273394890, metadata
  matching SPARTA II / IMO 9160994, identical latest-response control and
  an empty query from 08:00 UTC. `timestampExternal` is a source clock,
  not a verified vessel transmission time. No historical track
  or transmission-cessation inference is supported by these responses.
- IEM: 76 original EFHK/EETN METAR messages; redistribution and publication
  clocks are not known. Airport weather is not offshore weather.
- Estonia: the saved three-gauge query returned `[]`. No station-absence
  inference. Danish S3: an untruncated dated listing returned no keys.
  No 21 November Danish AIS ZIP was obtained or inspected.
- Copernicus: seven Sentinel-1 and seventeen Sentinel-2 catalogue records
  intersect the broad query rectangle; no image pixels were obtained or
  analysed. Whole-tile cloud percentages do not establish local visibility.
- EUMETSAT: seven original frame requests failed local DNS resolution.
  These are capture failures, not demonstrated archive gaps. No image
  was substituted from another date.
- Iltalehti and the Border Guard's ePressi statement: source links and
  retrieval receipts retained; article bodies and photos not republished.
  News clock labels remain attributed reporting, not sensor observations.

FMI and Fintraffic Digitraffic observations: CC BY 4.0; retain attribution.
Copernicus metadata, IEM messages and agency listings retain their source
attribution in receipts. Natural Earth context coastline is public domain.
The reported incident and the vessel's later path are not independently verified.

`python scripts/build_coastal_day.py --check` verifies original payload
hashes, units, station identities, complete requested label grids, raw
values, native/hourly agreement and the deterministic notebook offline.
The matching hash inventory is
`docs/design/coastal-day-20261121-provenance.json`. Original 11 November
packets and their provenance have not been regenerated. Later requests
must be stored as separate follow-ups, never over these saved responses.
