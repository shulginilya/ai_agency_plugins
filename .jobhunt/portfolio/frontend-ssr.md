---
project: Multi-brand furniture shopping platform (confidential employer)
slug: frontend-ssr
links: {}
period: 2018-07 – 2021-10
role: Lead frontend developer
confidential: true
sources: [/home/ilya-shulgin/web_projects/frontend-ssr, user]
---

# Furniture shopping platform — one Nuxt codebase, four markets

**A server-rendered shopping frontend that lets furniture shoppers in Germany, France, Italy and an international market search and filter a large catalogue, then click out to the retailer's shop.**

## The problem
The company ran furniture shopping sites under several brands and languages.
Each one needed fast, SEO-friendly pages over a large product catalogue, plus
filtering and search that let shoppers narrow the catalogue quickly. Shoppers
had to reach the right product before they were handed on to a partner shop.
Keeping a separate frontend per brand and language would have multiplied the
work for every feature and every fix.

## What I did
I was the lead frontend developer, working on the codebase from 2018 to 2021.
- Built the category and filter experience: price range, sort, facets, removing
  all filters at once, and breadcrumbs. These were the most-changed parts of
  the app.
- Moved search onto a new ElasticSearch query structure, and implemented
  autosuggestions in the search box.
- Worked on the SSR data layer: data loaders for each page type, plus the SEO
  head and breadcrumbs for each page type.
- Shipped features across all four language builds: the header, the product
  page, the home page, a new wishlist version, and switchable Google Shopping
  ads.
- Wrote and maintained the Jest unit specs (run per language) and the Cypress
  end-to-end tests, including the wishlist tests.

## How it works
A single Nuxt 2 / Vue codebase is built once per language and brand. A runtime
config picks the environment (dev, staging or production) and the language, and
each build ships as its own Docker image. A Vuex store and a query-builder
layer turn the shopper's filter state into ElasticSearch requests, facets and
suggestions. Pages render on the server for SEO, with lazy hydration on the
client. GitLab CI deploys a review environment for every branch and runs tests
after each deploy to review, staging and production, on Kubernetes. The hard
part was the search and filter layer. Every combination of filters had to
produce a correct query, the right facet counts and a crawlable URL, the same
way in four languages.

## Results
- One codebase served four language markets and several brand sites. Each new
  feature was built once and shipped to every brand.
- Category, product and search pages were rendered on the server, with SEO
  head data and breadcrumbs for each page type.
- Frontend changes went out through per-branch review environments, with unit
  tests and end-to-end tests after each deploy.

## Stack
Nuxt 2 · Vue 2 · Vuex · vue-i18n · SCSS · ElasticSearch · Auth0 · Jest ·
Cypress · Docker · Kubernetes · GitLab CI

---

## CV bullet
Lead frontend developer on a server-rendered (Nuxt/Vue) furniture shopping
platform serving 4 language markets from one codebase; built ElasticSearch
filtering, autosuggest and SEO page rendering.

## Platform blurb
Built the search and filtering experience for a multi-brand furniture shopping
platform. One server-rendered Nuxt codebase serves four European language
markets. As lead frontend developer (2018–2021) I owned the category and filter
UI (price range, sort, facets, breadcrumbs), moved search onto a new
ElasticSearch query structure, and added autosuggestions. I also built the SSR
data and SEO layer for each page type, and kept it covered with Jest and
Cypress tests in GitLab CI review environments.
Nuxt · Vue · Vuex · ElasticSearch · SCSS · Jest · Cypress · Docker · GitLab CI
