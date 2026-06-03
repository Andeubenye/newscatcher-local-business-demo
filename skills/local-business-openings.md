---
name: local-business-openings
description: Use this skill when asked to find new business openings
 in a specific city, town, district, county, region, or country anywhere
 in the world. Covers any business type -- restaurants, retail, cafes,
 healthcare clinics, gyms, entertainment venues, and more. Triggers on
 queries like "new businesses opening in [location]", "what's opening in
 [city]", "[business type] openings in [place]". Do NOT use for business
 closures, relocations, or general business news.
---

This skill finds structured event records about new local business
openings. It solves two things: how to write the right query, and what
data to extract from results. CatchAll returns events extracted from
articles -- not raw articles themselves. Every query must reflect this
distinction.

## When to use this skill

Use this skill when the request is for new businesses opening in a
specific location -- whether for local news coverage, sales prospecting,
or market intelligence. Works at any geographic scope worldwide: street,
city, district, county, region, or country.

## How to use this skill

Before constructing any query, determine whether the request is for
an event or an article. CatchAll extracts structured event records
from articles -- it does not retrieve articles themselves. Querying
for articles returns raw source content. Querying for events returns
clean structured data: what opened, where, when, and who runs it.

Always follow this formula: **[event type] + [specific location] +
[timeframe within 30 days]**

Example: `"grand opening restaurant Tokyo last 14 days"`

Then apply the validators and enrichments below to structure the output.

## Rules

**Never query for articles.** Phrases like "all news stories", "all
articles", or "NLP summary of the article" trigger article retrieval
instead of event extraction. Request event-level fields only.

**Event type must be specific.** Vague types like "business news" or
"local stories" will fail. Use "business openings", "restaurant
openings", or "retail store openings" instead.

**Timeframe must be within 30 days.** Queries exceeding this window
return unreliable results. Use explicit windows like "last 14 days"
or "last 30 days" rather than open-ended ranges like "since January".
For timeframes longer than 30 days, do not reject the query. Split it
into consecutive 30-day windows and run each separately, then combine
the results. A 3-month request becomes three queries: the first 30
days, the second 30 days, the third 30 days.

**Location must be explicit.** City, district, neighborhood, county,
region, country, or a named list of towns all work. Vague regional
terms do not.

## What counts as a valid opening

A result qualifies as a business opening only if it meets one of these
criteria:

- The business has **physically opened its doors** to paying customers
- An **opening event has been held** (grand opening, ribbon cutting, etc.)
- An **official opening date within the next 30 days has been announced**
 by the business or a credible source

These do **not** qualify:

- Rumors or speculation ("could be opening soon")
- Permit filings or zoning approvals with no stated opening date
- Construction updates or renovation notices without a confirmed date
- "Coming soon" signage or social media teasers with no specific date
- Online-only platforms, apps, or digital services with no physical location customers can visit
- Businesses located in a different city or region that merely reference the searched location in their article


The key test: is there a confirmed date or confirmed open status? If
not, exclude it.

## Validators

- `is_business_opening` -- true only if the event meets one of the three
 qualifying criteria above (physically open, event held, or official
 date within 30 days announced). False for rumors, permit filings,
 construction updates, or undated "coming soon" mentions.
- `location_match` -- true if opened in the specified location
- `event_in_timeframe` -- true if opening occurred or was announced
 within the specified window

## Enrichments

- `business_name` -- name of the opening business
- `business_type` -- restaurant, cafe, retail, clinic, gym, etc.
- `opening_date` -- confirmed or scheduled opening date
- `location_details` -- city, neighborhood, or street address
- `owner_operator` -- owner, chef, or operating company if mentioned
- `opening_qualifier` -- which qualifying criterion is met: `"now_open"`,
 `"event_held"`, or `"date_announced"`. Omit if `is_business_opening`
 is false.

## Fallback protocol when results are empty

If CatchAll returns zero results, do not give up. Escalate in steps,
and tell the user which fallback you're triggering before retrying.

**Step 1 -- Expand the timeframe.**
If the initial query used a window shorter than 30 days (e.g., "last 7
days" or "last 14 days"), retry with "last 30 days". Tell the user:
"No results found in the last [N] days -- expanding to 30 days."

**Step 2 -- Expand the geography.**
If Step 1 still returns nothing, widen the location scope by one level:
- neighborhood → full city
- city → metro area or county
- county → region or state/province
- city/region → whole country

Retry with the broader location and tell the user:
"Still no results for [original location] -- expanding to [broader area]."

**Step 3 -- Broaden the business type.**
If Step 2 still returns nothing and the original query targeted a
specific business type (e.g., "vegan restaurant"), retry with a broader
category (e.g., "restaurant", then "food and beverage"). Tell the user:
"Broadening business type from [specific] to [general]."

**Step 4 -- Report honestly.**
If all three fallback steps return nothing, tell the user: "No new
business openings were found for [location] in the past 30 days, even
after expanding the search. There may be limited coverage for this area
in the available sources."

Never silently expand scope. Always announce each fallback step so the
user understands what changed and can decide whether to accept the
broader results.

## Query signal terms

Include at least one of these phrases in your CatchAll query to signal
that you're looking for opening events, not general business news:

 grand opening, now open, opening soon, new location,
 opening its doors, soft opening

These are distinct from the business type (restaurant, clinic, gym) --
both should appear in the query. Example:

 `"grand opening restaurant [city] last 14 days"`


**Step 5 — Advise honestly.** "There may be limited public coverage for this location and timeframe."




