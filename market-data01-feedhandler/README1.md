# Harnessing Rapid Market Data: Crafting a High-Speed Binance Feed Server in C++

## **Introduction**

In the high-stakes world of financial markets, mere microseconds—or even nanoseconds—can determine the success or failure of a trade. It's undisputed: **low-latency and reliable** market data is paramount. The vast expanse of trading operations stretches across a complicated, **distributed** network of computational processes globally, each craving up-to-date market data. Within this web, enterprises employ a plethora of tools and technologies. To maintain coherence, **versatility and interoperability** across a wide spectrum of technologies becomes crucial. Furthermore, trading at its core is a competitive experimental science. The prowess of a market data platform in swiftly **capturing** and availing data for research and simulations is paramount for adaptive reactions to market flux.

The intricate balance of demands on trading technology is what transforms algorithmic trading into such a formidable and captivating endeavor. Our mission through this blog series is to conceptualize a market data platform that addresses these multifaceted requirements. In this inaugural entry, we'll delve deep into the low-latency facet of trading. Herein, we'll construct a rapid Binance Feed Server in C++, deploy multiple servers simultaneously for optimal load distribution, scrutinize the feed server's performance, and culminate with crafting a basic trade plotter via the Python API.

But why is swift market data indispensable in trading? Timely reactions to market swings are crucial. A tardy trading strategy risks outdated data, jeopardizing its efficiency by the time orders penetrate the market. Contemporary trading is fiercely competitive, where immediate action on lucrative trades holds the key. Conversely, sluggish strategies risk "adverse selection"—settling for trades discarded by others. Data lags can lead to packet loss, skewing market perspectives and potentially causing data backlogs—particularly in non-parallelizable strategies. An efficient market data system economizes resources. Imagine the fiscal contrast in operating five servers versus twenty; it resonates with both niche and large-scale entities.

## **Why Binance?**

Binance stands out for its accessible public interface and a user-friendly API. Numerous open-source feed handlers, designed for Binance and optimized for low latency, are at one's disposal. The principles of low-latency and elements concerning distribution and capture are largely synonymous across equity, futures, and FX market data streams.

## **Libwebsockets**

[Libwebsockets](https://github.com/warmcat/libwebsockets) emerges as a sleek, pure C library, masterfully crafted for hassle-free adoption of modern network protocols. Its lean footprint harnesses a non-blocking event loop, making it ideal for managing individual connections with an emphasis on message latency. Significantly, this library showcases a robust example for procuring Binance market data, which serves as our blueprint.

## **Featuremine Yamal**

[Yamal](https://github.com/featuremine/yamal) is an open-source marvel tailored for low-latency IPC and data capture. It's the linchpin for systems demanding rapid, consistent, and reliable inter-process communication. This is pivotal in arenas demanding swift and dependable data transition and retention—like financial trading platforms or real-time analytics mechanisms. Yamal's key features for our context include:
- **Performance**: Impressively low latencies - 300ns (median) and 1us (max) on a Ryzen 5950X.
- **Atomicity**: Guarantees either a complete or no bus update.
- **Consistency**: Ensures data uniformity across varying processes.
- **Resilience**: Retains data integrity despite application crashes.
- **Zero-copy**: Eliminates data duplication during read/write operations.
- **Simplicity**: Offers a streamlined C API and Python API.

Harnessing these features, we can seamlessly develop a feed server to distribute market data to other processes within the same system at breakneck speeds. For a more in-depth understanding of Yamal, visit https://github.com/featuremine/yamal.

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