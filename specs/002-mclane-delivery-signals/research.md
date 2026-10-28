# Research: McLane delivery signals

- **PC*MILER in TMW**: TMW plans loads with PC*MILER miles (practical by default). Trimble PC*MILER Web
  Services exposes REST at `https://pcmiler.alk.com/apis/rest/v1.0/Service.svc`, e.g.
  `route/routeReports?stops=lon,lat;lon,lat&reports=Mileage`, authenticated with an API key
  (`Authorization` header or `authToken`). Route options vary by account, so they are passed through
  `PCMILER_EXTRA_PARAMS`. Decision: keep warehouse PC*MILER miles as the source of truth; use live calls only
  for re-routes, and label any fallback.
- **Geofence auto-arrival**: telematics providers raise arrive / depart events when a truck enters a
  location geofence; bad geocodes are the most common reason they do not fire. Decision: store events in
  `geofence_events`, track `arrival_source` on stops, and suggest coordinates from stationary ELD pings.
- **Restaurant OTD**: restaurants commonly reject or penalize early arrivals (no staff, key drops),
  while retail stores accept early freight. Decision: channel-specific `otd_flag` with a 15-minute grace.
- **Dwell change**: costed with a truck-hour rate (driver + equipment) rather than detention billing,
  because most dwell is under the 2-hour free time.
