# Facebook Conversions API Tag for GTM Server Side, with BigQuery logging

A fork of [`stape-io/facebook-tag`](https://github.com/stape-io/facebook-tag),
maintained by [ROAS Architects](https://roasarchitects.com), that keeps the
template's BigQuery logging in place.

Everything else is upstream's. The tag sends server-side Facebook Conversions
API events built from Universal Analytics or GA4 requests inside your server
container, exactly as it does upstream. This fork adds one thing: every request
it sends and every response it gets back are written to a BigQuery table you own.

## Why we forked this

Stape's template is good work, and it is Apache 2.0, which is why a fork like
this is possible at all. Between 2026-05-26 and 2026-07-01 they removed
BigQuery logging from their server-side tag fleet as part of a wider refactor.
For this template that is commit
[`6769a59`](https://github.com/stape-io/facebook-tag/commit/6769a59). Console
logging stayed. For a template that has to run in anybody's container, carrying
a BigQuery dependency most installs never switch on is a fair thing to drop.

We need it, for a reason that is specific to how we work rather than a
criticism of that decision. A server-side tag fails quietly. There is no browser
console to check and no user to complain. It keeps returning success to the
container while the platform on the other end rejects everything it sends, and
that can run for a day before anybody notices, because noticing depends on a
person deciding to go and look. When it happened to us, the tag we could not
diagnose was the one with no log table behind it. Its siblings, still logging,
we could simply query.

So this fork restores the logging by reverting that one commit. The revert
applies with no conflicts, because upstream has not changed the template since.

## What gets logged

This is the part upstream never wrote down, and the reason we keep the fork
rather than a private patch. If you install this template, you should be able to
read what lands in your table without reading the source.

### The table

Create it once, in a dataset the container can write to:

```sql
CREATE TABLE `your_project.your_dataset.your_table` (
  timestamp            INT64,
  tag_name             STRING,
  type                 STRING,
  trace_id             STRING,
  event_name           STRING,
  request_method       STRING,
  request_url          STRING,
  request_body         STRING,
  response_status_code INT64,
  response_headers     STRING,
  response_body        STRING
);
```

| Column | What goes in it |
| --- | --- |
| `timestamp` | Milliseconds since epoch, taken when the row is built, not when the request was sent |
| `tag_name` | Always `Facebook` for this template. Sibling tags write their own name, so one table can hold a whole container |
| `type` | `Request`, `Response`, or `Message` |
| `trace_id` | The container's `trace-id` request header. This is what joins a request row to its response row, and to rows written by other tags for the same incoming event |
| `event_name` | The Facebook event name, for example `Purchase` |
| `request_method` | Always `POST` |
| `request_url` | The Graph API endpoint, including the pixel ID. The access token and app secret proof are masked to first four and last four characters, so you can tell two credentials apart without holding either |
| `request_body` | The full event payload sent to Facebook, as JSON |
| `response_status_code` | Facebook's HTTP status. Empty when the request never completed |
| `response_headers` | Facebook's response headers, as JSON |
| `response_body` | Facebook's response body. On a failed or timed-out request this instead holds the failure text, since there is no response to record |

> **This differs from upstream.** Upstream logs the endpoint verbatim, and the
> Graph API takes the access token as a query parameter, so an upstream log table
> holds live credentials in plain text. We mask them. See below.

### When rows are written

Three log points, all of them in the send path:

1. **Request**, immediately before each call to Facebook. One row per pixel, so
   a multipixel setup writes one Request row per configured pixel.
2. **Response**, when the call comes back, whatever the status. A 400 from
   Facebook is a `Response` row with `response_status_code = 400` and Facebook's
   error in `response_body`. This is the row that makes a broken pixel visible.
3. **Message**, if the batch of requests fails as a whole rather than
   individually.

### Things worth knowing before you rely on it

- **Logging is off unless you turn it on.** Set *BigQuery logging* to `Always`
  and fill in the project, dataset and table. There is no debug-only mode for
  BigQuery, unlike console logging.
- **BigQuery logging and console logging are independent.** Setting one does
  nothing to the other.
- **Optimistic mode suppresses the Response rows.** With *Optimistic scenario*
  on, the tag calls `gtmOnSuccess()` and stops caring about the reply, so you
  get Requests with no Responses. If you want to see what Facebook said, leave
  it off.
- **A tag that exits early logs nothing.** Consent denied, or an event the tag
  decides not to send, produces no rows at all. An empty table means "nothing
  was sent", which is not the same as "nothing was received".
- **Rows are inserted with `ignoreUnknownValues`.** A column missing from your
  table does not raise an error, it silently drops that field. If a column looks
  permanently empty, check the table schema before you check the code.
- **Inserts are streamed.** Freshly written rows sit in the streaming buffer, so
  a query with a partition filter can miss the last few minutes.

## Enabling it

In the tag's *Logs Settings*:

| Field | Value |
| --- | --- |
| BigQuery logging | `Always` |
| BigQuery project ID | your GCP project |
| BigQuery dataset ID | your dataset |
| BigQuery table ID | your table |

The container needs write access to that table. On Stape-hosted containers this
is wired for you. Self-hosted, the sandboxed BigQuery API resolves application
default credentials, so the container's own service account needs
`bigquery.tables.updateData` on the table. Streaming inserts do not need the
BigQuery Job User role.

## Three changes we made while restoring it

Both are small, and both are visible in the diff against upstream's last logging
version.

1. **Failure text is written to `response_body`.** The original failure path put
   its diagnostics in fields called `Message` and `Reason`. Neither has a
   column, so with `ignoreUnknownValues` a timeout landed a row with the
   diagnostics gone and every response field empty. Folding the text into
   `response_body` keeps it, and `response_body` is empty on exactly that path.
2. **Credentials in `request_url` are masked.** The Graph API endpoint carries
   `access_token`, and `appsecret_proof` when it is enabled, as query
   parameters. Logged verbatim, a log table becomes a credential store, and so
   does any console output pasted into a support thread. We mask both to
   `EAAG...ZZZZ`, keeping four characters at each end so two credentials are
   still distinguishable, and mask anything twelve characters or shorter whole.
   Masking happens once, in `log()`, so it covers every destination and any log
   point added later. The request itself is unchanged and still carries the real
   token.
3. **Values that are already strings are not stringified again.**
   `sendHttpRequest` hands back `result.body` as a string, and stringifying it a
   second time wraps it in escaped quotes, which stops `JSON_VALUE()` from
   parsing rows that parse fine for other tags writing to the same table.

## How this fork tracks upstream

- `main` is a plain mirror of `stape-io/facebook-tag`. We do not commit to it.
- `bq-logging` is `main` plus the restored logging. `git diff main..bq-logging`
  is the whole of what we changed, and is the only fork documentation there is.
- Following an upstream release is `git rebase main` on `bq-logging`. We sync
  when we want something upstream has shipped, not on a schedule.
- CI checks that `template.tpl`'s embedded JS still matches `template.js`, and
  that the logging is still there. It is the one way a rebase can quietly undo
  the entire point of this repo.

If you do not query your tag logs, install upstream's template. It is the same
tag, with less to configure. This fork is for people who want the send path on
the record.

## How to use the tag

Upstream's documentation applies unchanged:

- [Facebook tag description](https://stape.io/facebook-tag-for-google-tag-manager-server-side/)
- [How to set up Facebook Conversion API](https://stape.io/how-to-set-up-facebook-conversion-api/)
- [Event deduplication for Facebook Conversion API](https://stape.io/how-to-set-up-facebook-event-deduplication-in-google-tag-manager/)
- [How to set up server side tagging: Universal Analytics, GA4, and Facebook Conversion API](https://stape.io/google-tag-manager-server-side-how-to-set-up-server-universal-analytics-ga4-and-facebook-conversion-api/)

## Open Source

The **Facebook Tag for GTM Server Side** is developed and maintained by the
[Stape Team](https://stape.io/) under the Apache 2.0 license. This fork is
maintained by [ROAS Architects](https://roasarchitects.com) under the same
license, and is not affiliated with or endorsed by Stape.
