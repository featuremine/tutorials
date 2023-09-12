# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Server in C++

## **Introduction**

In the realm of financial markets, milliseconds, if not microseconds, can spell the difference between a successful trade and a missed opportunity. There's no denying the significance of rapid and reliable market data.

### Importance of low-latency market data:
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

### Blog series goal:
Our objective with this series is to architect a lightning-fast market data platform that also meets distribution and capture benchmarks.

### Aim for this blog:
In this entry, we'll provide a blueprint for crafting a high-speed Binance feed server in C++ ensuring low-latency market data access for local consumers.

## **Why Binance?**
- **Accessibility**: Binance is renowned for its public availability and intuitive API.
- **Variety**: A plethora of implemented, open-source feed handlers exist for Binance, including those optimized for low latency.
- **Market Versatility**: Most facets of low-latency and nearly all elements pertinent to distribution and capture are applicable to equity, futures, and FX markets data feeds.

## **Libwebsockets**
Libwebsockets stands out as a nimble, pure C library tailored for crafting contemporary network protocols without a hassle. The library has a minuscule footprint and leverages a non-blocking event loop. Especially for our needs, it's apt for handling a single connection, focusing on the latency of each message. Notably, the library offers a comprehensive example for receiving Binance market data, serving as our foundation.

## **Featuremine Yamal**
Yamal, an open-source library, is geared towards transactional low-latency IPC and data capture. It's the cornerstone for systems necessitating swift and reliable data communication between various processes.

**Features**:
- **Performance**: Boasts a median latency of 300ns and a max latency of 1us on Ryzen 5950X.
- **Atomic**: Ensures the entire update to the bus is either done or not done at all.
- **Versatility**: Compatible with multiple producers and consumers.
- **Non-blocking**: Efficiently reserves and commits message memory.
- **Data Consistency**: Guarantees consistency across different processes.
- **Structured Data**: The data is housed in a flat file.
- **Sequential**: Ensures chronological order for message storage and access.
- **Reliability**: Post-crash, peers can function normally.
- **Zero-copy**: Abstains from data copying during read/write.
- **Ever-present Data**: Data pointers remain valid until application shutdown.
- **Additional Features**: Supports file rollover, indexing, random access, and boasts a simple C API alongside a Python API.

Yamal's features render it the ideal choice for constructing a high-performance market data platform aligning with the prerequisites discussed in the introduction.


-----------------------------------------------
# Unlocking Lightning-Speed Market Data: Building a Blazing Fast Binance Feed Server in C++

## **Introduction**

In the fast-paced realm of trading, time is a pivotal factor that often dictates success or failure. Low-latency market data is the gold standard for any market participant, but why is it so pivotal?

1. **Relevance of Information**: The more time a strategy takes to respond to market events, the less relevant the information will be once the order reaches the market. This time-lapse can often lead to trading strategies misfiring. A prime example is the perils of "adverse selection". If a strategy executes a trade slowly, it often means it was not the optimal trade since others bypassed it.

2. **Avoidance of Packet Loss**: Even if a strategy isn’t dictated by market events, slow data processing can lead to packet loss, thereby giving rise to flawed market data. Additionally, slow processing often causes exponential queuing, which further delays data access.

3. **Economical Operations**: Efficient market data platforms require fewer resources, translating to lesser operational costs. Imagine the significant financial difference between maintaining five versus twenty high-end servers.

4. **Efficient Distribution**: Market data platforms should be readily accessible to multiple endpoints, such as trading strategies, signal servers, and monitoring tools. Moreover, these platforms must guarantee low-latency while supporting various data routes without compromising on performance.

5. **Instant Capture**: This feature enables strategies to recall hours-worth of market data, thereby allowing them to reconstitute their state upon initiation. Plus, having almost real-time access aids in research and simulations.

In this series, our mission is to design a lightning-speed market data platform that seamlessly integrates these functionalities. Our focus today? A comprehensive guide on constructing a swift Binance feed server in C++.

## **Why Binance?**

Binance emerges as an excellent choice due to its public availability coupled with a user-centric API. The presence of numerous open-source feed handlers, especially the low-latency ones, add to its allure. Importantly, lessons from Binance can be seamlessly transposed to equity, futures, and FX market data feeds.

## **Libwebsockets**

Libwebsockets serves as a lean, pure C library, tailored for crafting modern network protocols with an insignificant footprint. This powerhouse is compatible with OpenSSL and is optimized for single connections, focusing on the latency of individual messages. An icing on the cake? Libwebsockets offers a comprehensive example of receiving Binance market data, offering us a sturdy foundation to build upon.

## **Featuremine Yamal**

Yamal, an open-source library, emerges as the linchpin for transactional low-latency IPC and data capture. The array of features it brings to the table include:

- **Performance**: Astoundingly low latencies - 300ns (median) and 1us (max) on a Ryzen 5950X.
- **Atomicity**: Ensures updates to the bus are consistent.
- **Non-blocking**: Ensures message memory is secured without obstructions.
- **Consistency**: Guaranteed data coherence across processes.
- **Sequencing**: Data access and storage follow a chronological trajectory.
- **Resilience**: In the event of crashes, operations remain uninterrupted.
- **Efficiency**: Zero-copy ensures no duplication during data read/write.
- **Availability**: Data pointers remain active until application closure.
- **Versatility**: Support for file rollover, indexing, and random access.
- **Simplicity**: Boasts an elementary C API and a Python API.

Given its feature-rich architecture, Yamal is a clear choice for our high-performance market data platform, aligning perfectly with the prerequisites outlined in our introduction.

**Stay Tuned**: In our subsequent posts, we will delve deeper into the intricacies of building this robust platform, ensuring that you stay ahead in the high-stakes game of trading.

------------------------------------------------------------------------------------------------------

# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Server in C++

## **Introduction**
1. Importance of low-latency market data:
   - The more time strategy takes to respond to market events, the less relevant the information will be by the time the order gets to the market.
   - Acting upon information available to multiple participants is competitive.
   - For example, strategy that is able to make a trade when the trade is expected to make a profit will make money.
   - The reserse is worse than not making money. Strategy that made a trade while being slow, likely means that it was a bad trade, because no one else wanted it. This is so called "adverse selection".
   - Even if strategy is not market event driven, slow processing will result in packet loss and thus bad marked data. - Slow processing results in exponential queuing that can also result in significantly delayed data. This is expecially the case in cross-sectional strategies where parallelizing the strategy is not possible.
   - lastly, high performance market data platform also results in less resources required to deploy it. Difference between running five or twenty very expensive servers is rather dramatic not only to small teams but to large enterprise also.
2. Easy and availability of distribution is another requirement for market data platforms:
   - Making market data available to various strategies, signal servers and monitoring tools is crucial.
   - Both low-latency and available range of destinations is important.
   - Fast signal server might require low-latency distribution.
   - The enterprise risk monitoring can utilize kafka-based feed.
   - It makes IT department's life easier if a wide range of programming languages and tools can access the market data.
   - It should also be easy to develop new tools and adapters to access or distribute the market data.
   - various market data routes should not affect each other's performance.
3. Finally capture is another important aspect of the market data platform.
   - making last several hours worth of market data available to the strategy to allow strategy to build up its state when starting up.
   - near real-time processing of market data for evaluation or research purposes.
   - near real-time market data archiving to make data available for research and simulation.
3. Blog series goal: Build a lighting-speed market data platform that also satisfies distribution and capture requirements.
4. Aim for this blog: Guide to building a fast Binance feed server in C++ that provides low-latency market data access to consumers on the local machine.

## **Why Binance?**
- Binance’s public availability and user-friendly API.
- wide range of implemented, open source feed handlers, including low-latency ones, at least as far as that can be managed for a websocket/SSL/json feed.
- Many aspects of low-latency and nearly everything related to distribution and capture is relevant to equity, futures, and FX markets data feeds.

## **Libwebsockets**
- libwebsockets is a flexible, lightweight pure C library for implementing modern network protocols easily with a tiny footprint, using a nonblocking event loop. It support OpenSSL and has good performance when used for a single connection as we do for here. For our applications we care about latency of each message on a single connection as opposed to a server designed to process multitude of requests from various clients.
- The library also provides complete example for receiving Binance market data, which we use as a foundation.

## **Featuremine Yamal**
- Yamal is an open source library for transactional low-latency IPC and data capture. It is used to build systems where data is communicated and captured between different processes very quickly, with an emphasis on ensuring the consistency and reliability of that data. This is especially important in environments where fast, reliable data transmission and storage are essential, such as financial trading platforms or real-time analytics systems.
- Performance: 300ns (median latency), 1us (max latency) on Ryzen 5950X.
- Atomic: A guarantee of atomicity prevents updates to the bus occurring only partially.
- multi-producer and multi-consumer
- Non-blocking: Message memory is reserved and committed without blocking.
- Data consistency across processes.
- Serialized: Data is contained in a flat file.
- Sequential: Message access and storage are in a chronological order.
- Persistent: Upon a crash, peers can continue to operate normally.
- Zero-copy: data is not copied during writing or reading.
- Availability: Data pointers stay valid at all times until application shutdown
- Supports file rollover
- Supports indexing and random access
- Simple C API
- Python API
These features make Yamal perfect as a foundation for the high-performance market data platform that full requirements discussed in the introduction

------------------------------------------------------------------------------------------------------

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