# Epsilon tuning log

Epsilon starts as an exact copy of Delta's settings ([models/epsilon.json](../../models/epsilon.json))
and is tuned on paired practice weeks against Delta. Goal: enough margin per week to reach the
top 7 on the official board while every week stays above 90% on time.

| Step | Change | Paired weeks | Margin vs Delta / week | Positive weeks | Worst on time | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | Delta settings, unchanged | — | reference | — | — | baseline |
