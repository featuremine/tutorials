# Building a Lightning-Fast Binance Feed Server with C++

## **Introduction**

In the intricate world of financial markets, every microsecond counts. The difference between seizing an opportunity or missing it can be a matter of nanoseconds. There's no contesting the value of **low-latency and dependable** market data. Trading, a vast and often globally **distributed** network of computational processes, necessitates this data. Amidst this expansive trading ecosystem, compatibility and smooth communication with a plethora of technologies is paramount. Moreover, in this competitive domain, a market data platform's capability to swiftly **capture** and present data for research and simulations is crucial for deciphering and adapting to ever-changing market scenarios.

The plethora of requirements makes algorithmic trading a complex yet riveting endeavor. Our goal in this blog series is to design a market data platform that ticks all the boxes. In this initial installment, we delve into crafting a low-latency Binance Feed Server using C++, evaluate its performance, deploy multiple servers for load balancing, and finally, showcase a basic trade plotter via a Python API.

The significance of real-time market data cannot be overstated. Immediate responses to market changes are imperative. If there's a delay in a strategy's execution, the data might be obsolete by the time the order lands on the market floor. Consequently, a speedy strategy might be the difference between seizing a golden opportunity or settling for an "adverse selection". Besides, lags can lead to data loss, creating a skewed market perspective and potential data congestion. An efficient market data system, aside from being faster, is also cost-effective. Imagine the cost difference between running five servers compared to twenty - it affects everyone, from startups to conglomerates.

## **Why Binance?**
Binance's reputation stems from its easily accessible and user-friendly API. A myriad of open-source feed handlers optimized for low latency have been crafted for Binance. It's worth noting that the principles of low-latency, distribution, and data capture are universally applicable across equity, futures, and FX market data feeds.

## **Libwebsockets**
[Libwebsockets](https://github.com/warmcat/libwebsockets) is a lean, pure C library designed to facilitate modern network protocols. This compact library integrates a non-blocking event loop, making it ideal for managing a singular connection with a keen emphasis on each message's latency. Notably, it provides an extensive example for accessing Binance market data, which serves as our stepping stone.

## **Featuremine Yamal**
[Yamal](https://github.com/featuremine/yamal) is an open-source library fine-tuned for transactional low-latency IPC and data capture. Primarily used in systems that demand rapid and consistent data exchange between varied processes, it shines in settings like financial trading platforms or real-time analytics. Yamal's features relevant to our discussion include:
- **Performance**: Remarkably low latencies - 300ns (median) and 1us (max) on a Ryzen 5950X.
- **Atomicity**: Guarantees either complete execution or none at all.
- **Consistency**: Ensures uniform data across diverse processes.
- **Resilience**: Data preservation even during application failures.
- **Zero-copy**: Bypasses data duplication during read/write operations.
- **Simplicity**: Offers a straightforward C and Python API.

Leveraging these features, we can efficiently develop a feed server that transmits market data to other processes on the same machine at unparalleled speeds. To delve deeper into Yamal, visit [here](https://github.com/featuremine/yamal).

## **Constructing the Binance Feed Server**

### **Getting Started**

To facilitate this tutorial, I've created a repository containing all essential code snippets. Before diving in, ensure you've installed [git](https://git-scm.com/downloads), [CMake](https://cmake.org/download), and a C++ compiler toolchain. This project is compatible with contemporary Linux and MacOS setups. For Windows users, consider using either the Windows Subsystem for Linux (WSL) or a Docker container.

Kick off by cloning the repository and setting up the build environment:
```bash
git clone --recurse-submodules https://github.com/featuremine/tutorials
cd tutorials
cmake -B release -DCMAKE_BUILD_TYPE=Release
cmake --build release
```
Post-build, locate the tutorial binaries under **release/market-data01-feedhandler**.

### **Decoding the libwebsocket Binance Sample**

To streamline the process, we've imported the Binance sample from libwebsocket into our tutorial repository. The file in focus is [minimal-ws-client-binance.c](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/minimal-ws-client-binance.c).

Take a moment to examine how the server and desired Binance streams are specified on line [minimal-ws-client-binance.c:130](https://github.com/featuremine/tutorials/blob/ba5e6cda40f924b14019a483688ef52c22b07b2a/market-data01-feedhandler/minimal-ws-client-binance.c#L130):
```C
i.address = "fstream.binance.com";
i.path = "/stream?streams=btcusdt@depth@0ms/btcusdt@bookTicker/btcusdt@aggTrade";
```
Data from Binance, structured in JSON, is processed at line [minimal-ws-client-binance.c:247](https://github.com/featuremine/tutorials/blob/2f4257e82a68a69a24d3e63805610a0f5e113844/market-data01-feedhandler/minimal-ws-client-binance.c#L247). Despite being in JSON format, Binance's message structure remains consistent, negating the need for a comprehensive JSON parser. Familiarize yourself with the [Binance API docs](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams) for further clarity. Within the code, `lws_json_simple_find` aids in locating the JSON key, a function we'll also employ in our application.

### **Integrating Yamal**

Initially, I duplicated [minimal-ws-client-binance.c](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/minimal-ws-client-binance.c) to [binance-feed-handler.cpp](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/binance-feed-handler.cpp). This separation ensures our additions pertaining to Yamal won't interfere with the original code. This feed handler is converted into a C++ application, facilitating the use of the C++ standard library.

Following this, I introduced command-line argument processing. Refer to [binance-feed-handler.cpp:313](https://github.com/featuremine/tutorials/blob/ff04f928715f00fbd06ab0271280519029d4ba78/market-data01-feedhandler/binance-feed-handler.cpp#L313) for clarity. Here, the `fmc_cmdline_opt_proc` utility, sourced from our Featuremine Common Library `libfmc`, comes in handy. This library is also accessible in the [Yamal repository](https://github.com/featuremine/yamal). 

After this, I loaded securities from the file, with an additional step to eliminate potential duplicates:
```c++
// Loading securities from the file
vector<string> secs{istream_iterator<string>(secfile), istream_iterator<string>()};
// Sorting securities
sort(secs.begin(), secs.end());
// Eliminating duplicate securities
auto last = unique(secs.begin(), secs.end());
secs.erase(last, secs.end());
```
The subsequent steps involve reading and writing the YTP file, initializing an instance of Yamal, and utilizing the `ytp_yamal_new` function. Notably, error-checking is crucial at each stage to ensure smooth operation.

Yamal, in essence, is a series of memory-mapped linked lists. This architecture delivers impressive performance while retaining adaptability. A data-driven list is used alongside another defining the logical data segmentation into `streams`. The `Stream` is effectively a combination of a `peer` and `channel`. Here, `peer’ indicates the data publisher, and `channel` represents a global data category.

For our project, each Binance stream is channeled to a distinct YTP channel. Stream definition necessitates an instance of the streams object. Subsequently, for every security and required Binance feed (specifically `bookTicker` and `trade`), a relevant YTP stream is announced.

Towards the end, data received from Binance is written to Yamal. The initial step entails identifying the Binance stream name, followed by the actual update data from the message. Post this identification, the relevant YTP stream is identified, and the data is recorded.

### **Validating and Assessing Performance**

Now, it's time to test our feed handler in action. For this exercise, I've prepared two files, each containing a curated list of securities. To start, run one feed handler instance:

```bash
./release/market-data01-feedhandler/binance-feed-handler --securities market-data01-feedhandler/securities1.txt --peer feed --ytp-file mktdata.ytp
```

For direct content verification, Yamal tools are essential. Within the scope of this tutorial, these utilities are incorporated during the project build. But for general use, you can either fetch from the [releases](https://github.com/featuremine/yamal/releases) or build directly from the source.

The `yamal-tail` tool can be used to display the file contents:
```bash
./release/dependencies/build/yamal/yamal-tail mktdata.ytp
```
Following this, launch another feed handler with a different set of securities. Then, deploy `yamal-stats` to confirm that streams related to this new set of securities are present in Yamal. Finally, employ `yamal-local-perf` to monitor Yamal's performance.

### **Data Integration for Trade Visualization**

Concluding this tutorial, I'll guide you on leveraging the market data from Yamal. I've developed a concise Python script that illustrates a series of trades, complemented by the best bid and offer available during the trade.

To set up the Python environment, simply run:
```bash
pip install -r requirements.txt
```
Run the script with your preferred backend (in this example, we use GTK4Cairo for matplotlib):

```bash
MPLBACKEND=GTK4Cairo python market-data01-feedhandler/binance-view.py --ytp-file mktdata.ytp --security btcusdt --points 1000
```
The outcome is a graphical

 display of trade data, reinforcing the practical utility of the market data collected from Binance.

### **Conclusion**

By following this tutorial, you've built a comprehensive Binance feed server that captures, processes, and visualizes market data. The integration of Yamal into your C++ application equips you with the potential to manage high-frequency data efficiently. Going forward, you can adapt this foundational codebase to cater to a broad spectrum of trading applications and analytics tools. Happy coding!