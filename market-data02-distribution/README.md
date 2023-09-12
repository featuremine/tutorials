# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Server in C++

## **Introduction**

In the realm of financial markets, microseconds, if not nanoseconds, can spell the difference between a successful trade and a missed opportunity. There's no denying the importance of **low-latency and reliable** market data. Trading operations, however, is a large, complex, (often globally) **distributed**, graph of computational processes and most of them require market data in one form or another. Enterprises often have a diverse ecosystem of tools and technologies utilized by these processes and **versatility and interoperability** with meriad of technologies is a key requirements. At the same time, trading is ultimately is a competitive experimental science and ability of the market data platform to **capture** market data and quickly make it available for research and simulations is essential for analysing and responding to latest market conditions.

The multitude of seemingly contrudictory requirements placed on trading technology is what ultimatey makes algorithmic trading such a challenging, yet facinating persuit. Our objective with this series of blogs is to architect a market data platform that meets all four of the requirements mentioned above. In this, first installment, of the series we will focus on:
- low latency
- load balancing
- local distribution
- Python API and easy of use

## Why low-latency market data is so important in trading?
- **Relevance**: The more time a strategy takes to respond to market events, the less relevant the information will be by the time the order gets to the market.
- **Competition**: Acting upon information available to multiple participants is fiercely competitive.
- **Profitable Decisions**: A strategy that can promptly capitalize on a trade expected to yield profit will earn money.
- **Adverse Selection**: Conversely, if a strategy is too slow, it's likely making an undesirable trade that no one else sought—this is referred to as "adverse selection".
- **Data Integrity**: Slow processing can lead to packet loss and consequently, flawed market data. It can also cause exponential queuing, leading to substantially delayed data, particularly for cross-sectional strategies where parallelization isn’t feasible.
- **Resource Efficiency**: A high-performance market data platform demands fewer resources. The cost difference between running five servers or twenty can be monumental, affecting both small teams and large enterprises.

### Easy and availability of distribution is another requirement for market data platforms:
- **Versatility**: Making market data available to diverse strategies, signal servers, and monitoring tools is vital.
- **Dual Needs**: Both low-latency and a broad spectrum of destinations are crucial.
- **Requirements**: While a fast signal server might mandate low-latency distribution, an enterprise risk monitor could leverage a kafka-based feed.
- **Interoperability**: The IT department has it easier when various programming languages and tools can readily access the market data.
- **Expandability**: It should be straightforward to devise new tools and adapters to access or disseminate the market data.
- **Performance Independence**: Different market data routes must not impair each other's efficiency.

### Capture is another important aspect of the market data platform:
- **Data Reservoir**: It's crucial to have several hours of market data available for strategies to initialize their state upon launch.
- **Research and Analysis**: Near real-time processing of market data is pivotal for evaluation, research, and subsequent data archiving to facilitate further studies and simulations.
- **Near real-time archive**: Ability to archive market data nearly real-time, allows research teams to analyse startegy performance and to make model adjustments for the following trading day.

## **Why Binance?**
- **Accessibility**: Binance is renowned for its public availability and intuitive API.
- **Variety**: A plethora of implemented, open-source feed handlers exist for Binance, including those optimized for low latency.
- **Market Versatility**: Most facets of low-latency and nearly all elements pertinent to distribution and capture are applicable to equity, futures, and FX markets data feeds.

## **Libwebsockets**
Libwebsockets stands out as a nimble, pure C library tailored for crafting contemporary network protocols without a hassle. The library has a minuscule footprint and leverages a non-blocking event loop. Especially for our needs, it's apt for handling a single connection, focusing on the latency of each message. Notably, the library offers a comprehensive example for receiving Binance market data, serving as our foundation.

## **Featuremine Yamal**
Yamal, an open-source library, is geared towards transactional low-latency IPC and data capture. It's the cornerstone for systems necessitating swift and reliable data communication between various processes.

**Features**:
- **Performance**: Astoundingly low latencies - 300ns (median) and 1us (max) on a Ryzen 5950X.
- **Atomicity**: Ensures the entire update to the bus is either complete or not done at all.
- **Sequential**: Ensures chronological order for message storage and access.
- **Versatility**: Support for file rollover, indexing, and random access.
- **Resilience**: In the event of application crashes, data is not lost.
- **Structured Data**: The data is housed in a flat file.
- **Simplicity**: Boasts an elementary C and Python API.
- **Non-blocking**: Ensures message memory is secured without obstructions.
- **Consistency**: Guarantees data consistency across different processes.
- **Zero-copy**: Abstains from data copying during read/write.
- **Availability**: Data pointers remain active until application closure.
- **Discovery**: designed for on-demand data and data discovery.

Yamal's features render it the ideal choice for constructing a high-performance market data platform aligning with the prerequisites discussed in the introduction.

## **Building the Binance Feed Server**

1. **Setup**
   - Create a C++ development environment.
   - Install libwebsockets and Featuremine Yamal.

2. **Websocket Connection**
   - Connect to Binance’s websocket API.

3. **Stream Market Data**
   - Customize data stream: trades, ticker data, order books.

4. **Serialization**
   - Transform market data for serialization.
   - Use Featuremine Yamal for serialization.

5. **Inter-process Communication (IPC)**
   - Transmit serialized data between processes.

### **Optimizations**
- Consider fine-tuning data structures, multithreading, and network settings.

### **Conclusion**
- Combine C++, libwebsockets, and Featuremine Yamal for real-time market data.

### **Feedback**
- Encourage readers to share feedback and experiences.

### **References & Acknowledgements**
- Appreciate libwebsockets and Featuremine Yamal creators.

---
Setup:
Create a C++ development environment.
Install libwebsockets and Featuremine Yamal.
Initialize the Websocket Connection:
Connect to Binance’s websocket API.
Stream Market Data:
Configure websocket for specific data: trades, tickers, order books.
Serialization with Featuremine Yamal:
Convert market data for serialization.
Serialize using Featuremine Yamal.
Inter-process Communication:
Transmit serialized data using Featuremine Yamal.
Potential Optimizations

Consider fine-tuning data structures, multithreading, and network settings.
Conclusion

Emphasize benefits of using C++, libwebsockets, and Featuremine Yamal for real-time data access.
Feedback Galore

Encourage reader feedback and sharing of experiences.
References and Acknowledgements

Credit to libwebsockets and Featuremine Yamal creators.

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
1.
    ```
    ./market-data01-feedhandler/binance-feed-handler --securities ../market-data01-feedhandler/securities.txt --peer feed --ytp-file mktdata.ytp
    ```
1. To check content directly, install yamal and run yamal-tail (need to improve readme on how to build and install yamal)
1. C++ program to measure performance
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