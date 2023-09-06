# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Handler in C++

## Indroduction

Welcome to the inaugural blog in our in-depth series focused on building a cutting-edge market data platform. Whether you're a small team, a burgeoning enterprise, or anywhere in between, the challenges of efficiently handling market data are universal. With the dynamic world of cryptocurrencies being the most accessible for many, we've chosen the Binance market as our starting point. But don't let the simplicity fool you &mdash; while the raw speed of our crypto feed handler might seem like overkill now, the methodologies and design principles we delve into will be equally applicable in the realms of equities, futures, and FX. As we take this journey together, we'll be leveraging the power of Featuremine Yamal, a versatile tool that doubles as both an efficient storage format and a high-octane messaging bus. So, whether you're laying the first bricks of your market data platform or retrofitting an existing structure, buckle up! This series promises deep dives, actionable insights, and best of all, blistering speeds!

1. Start with libwebsockets binance example
1. Copy to binance-feed.cpp and add TCAP

## Setup
### pull repo with submodules, using cmake utils
### using easywsclient and json added using cmake
### Create a simple program that gets Binance BBO feed
### Add Binance Trades feed
### Introduction to yamal and why we need something like yamal
### Normalize or not normalize (both)
### add parsing part from file
### Summary and conclusions and next steps