# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Handler in C++

## Indroduction

Welcome to the inaugural blog in our in-depth series focused on building a cutting-edge market data platform. Whether you're a small team, a burgeoning enterprise, or anywhere in between, the challenges of efficiently handling market data are universal. With the dynamic world of cryptocurrencies being the most accessible for many, we've chosen the Binance market as our starting point. But don't let the simplicity fool you &mdash; while the raw speed of our crypto feed handler might seem like overkill now, the methodologies and design principles we delve into will be equally applicable in the realms of equities, futures, and FX. As we take this journey together, we'll be leveraging the power of Featuremine Yamal, a versatile tool that doubles as both an efficient storage format and a high-octane messaging bus. So, whether you're laying the first bricks of your market data platform or retrofitting an existing structure, buckle up! This series promises deep dives, actionable insights, and best of all, blistering speeds!

1. Start with libwebsockets binance example
1. Copy to binance-feed-handler.cpp and add comman line argument parsing.
1. Add command line argument for securities file and parse securities file into subscription string.
    ```c++
    ostringstream ss;
    ss << "/stream?streams=";
    for (std::string line; std::getline(secfile, line); ) {
        ss << line << "@bookTicker/" << line << "@trade";
    }
    ```
1. Just print data for now
    ```c++
    write(STDOUT_FILENO, (const char *)in, len);
    printf("\n");
    ```
1. Identify stream use string_view.
1. Why Yamal: low-latency, multi-producer, multi-consumer, flat format, distributable
1. Using string_view for keys because performance
1. Add small script to read data and plot it.
1. C++ program to measure performance
1.
    ```
    ./market-data01-feedhandler/binance-feed-handler --securities ../market-data01-feedhandler/securities.txt --peer feed --ytp-file mktdata.ytp
    ```
1. To check content directly, install yamal and run yamal-tail
1.
    ```bash
    MPLBACKEND=GTK4Cairo python ../market-data01-feedhandler/binance-view.py --ytp-file mktdata.ytp --security btcusdt
    ```

## Setup
### pull repo with submodules, using cmake utils
### using easywsclient and json added using cmake
### Create a simple program that gets Binance BBO feed
### Add Binance Trades feed
### Introduction to yamal and why we need something like yamal
### Normalize or not normalize (both)
### add parsing part from file
### Summary and conclusions and next steps