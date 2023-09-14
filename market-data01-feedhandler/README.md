# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Server in C++

## **Introduction**

In the realm of financial markets, microseconds, if not nanoseconds, can spell the difference between a successful trade and a missed opportunity. There's no denying the importance of **low-latency and reliable** market data. Trading operations, however, is a large, complex, (often globally) **distributed**, graph of computational processes and most of them require market data in one form or another. Enterprises often have a diverse ecosystem of tools and technologies utilized by these processes and **versatility and interoperability** with meriad of technologies is a key requirements. At the same time, trading is ultimately is a competitive experimental science and ability of the market data platform to **capture** market data and quickly make it available for research and simulations is essential for analysing and responding to latest market conditions.

The multitude of seemingly contrudictory requirements placed on trading technology is what ultimatey makes algorithmic trading such a challenging, yet facinating persuit. Our objective with this series of blogs is to architect a market data platform that meets all four of the requirements mentioned above. In this, first installment, of the series we will focus on building a low-latency Binance Feed Server in C++, we will deploy several of them at once for load balancing, then we will evaluate performance of the feed server, and finally we will implement a simple trade plotter using Python API.

Why is quick market data crucial in trading? Quick responses to market shifts are vital. If a trading strategy lags, the data might be outdated by the time the order reaches the market. Trading based on timely information is super competitive. A strategy that acts fast on profitable trades will benefit. On the flip side, a slow strategy might end up with trades no one else wanted, known as "adverse selection". Delays can result in lost data packets, giving an inaccurate market view. This can also cause data backlogs, especially in strategies where market data processing can't be parallelized. A top-notch market data system uses fewer resources. Think of the huge cost difference between operating five servers versus twenty – it impacts both small groups and big businesses.

## **Why Binance?**
Binance is renowned for its public availability and intuitive API. A plethora of implemented, open-source feed handlers exist for Binance, including those optimized for low latency. Most facets of low-latency and nearly all elements pertinent to distribution and capture are applicable to equity, futures, and FX markets data feeds.

## **Libwebsockets**
[Libwebsockets](https://github.com/warmcat/libwebsockets) stands out as a nimble, pure C library tailored for using contemporary network protocols without a hassle. The library has a minuscule footprint and leverages a non-blocking event loop. Crucially for our objectives, it's well-suited to manage a singular connection, emphasizing the latency of every message. Importantly, the library provides a detailed example of accessing Binance market data, serving as our foundation.

## **Featuremine Yamal**
[Yamal](https://github.com/featuremine/yamal), an open-source library, is geared towards transactional low-latency IPC and data capture. It is used to build systems where data is communicated and captured between different processes very quickly, with an emphasis on ensuring the consistency and reliability of that data. This is especially important in environments where fast, reliable data transmission and storage are essential, such as financial trading platforms or real-time analytics systems. The features of Yamal that are relevant for this blog are:
- **Performance**: Astoundingly low latencies - 300ns (median) and 1us (max) on a Ryzen 5950X.
- **Atomicity**: Ensures the entire update to the bus is either done or not done at all.
- **Consistency**: Guarantees data consistency across different processes.
- **Resilience**: In the event of application crashes, data is not lost.
- **Zero-copy**: Abstains from data copying during read/write.
- **Simplicity**: Boasts an elementary C API and Python API.

These features will easily allow us to create feed server to distribute market data to other process on the same machine at blazing fast speed. To learn more about Yamal visit https://github.com/featuremine/yamal.
## **Building the Binance Feed Server**

### **Setup**
For the purpose of this tutorial, I have created a repo where you can find all of the relevant code. To start out you will need [git](https://git-scm.com/downloads), [CMake](https://cmake.org/download) and a C++ compiler toolchain. The project builds on most sufficiently up-to-date Linux and MacOS systems. If you would like to build it on Windows I recommend using either WSL or a docker container.

Begin by checking out the repo, creating a build directory, configuring the project with cmake and building it.
```bash
git clone --recurse-submodules https://github.com/featuremine/tutorials
cd tutorials
cmake -B release -DCMAKE_BUILD_TYPE=Release
cmake --build release
```
Now, you will be able to find the binaries for this tutorial in **release/market-data01-feedhandler**.

### **libwebsocket Binance example**
To simplify things we copied the Binance example from libwebsocket [minimal-ws-client-binance.c](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/minimal-ws-client-binance.c) to the tutorial repo.
For our purposes here we should take note of how to specify the server and Binance streams to which we want to subscribe on line [minimal-ws-client-binance.c:130](https://github.com/featuremine/tutorials/blob/ba5e6cda40f924b14019a483688ef52c22b07b2a/market-data01-feedhandler/minimal-ws-client-binance.c#L130):
```C
i.address = "fstream.binance.com";
i.path = "/stream?"
        "streams=btcusdt@depth@0ms/btcusdt@bookTicker/btcusdt@aggTrade";
```
On line [minimal-ws-client-binance.c:247](https://github.com/featuremine/tutorials/blob/2f4257e82a68a69a24d3e63805610a0f5e113844/market-data01-feedhandler/minimal-ws-client-binance.c#L247) of the example is where the data from Binance is being processed. Binance market data comes in JSON format, however, messages have a strictly prescribed structure. This makes parsing these messages quite easy and in general does not require a full-blown JSON parser. You can refer to [Binance API docs](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams) for more details. LWS is using `lws_json_simple_find` to find the location of JSON key. We will also use this function in our application.
```C
case LWS_CALLBACK_CLIENT_RECEIVE:
    // ...
    p = lws_json_simple_find((const char *)in, len,
                    "\"depthUpdate\"", &alen);
```

### **Adding Yamal**
First, I copied [minimal-ws-client-binance.c](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/minimal-ws-client-binance.c) to [binance-feed-handler.cpp](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/binance-feed-handler.cpp) so that Yamal related changes could be added without interfering with the original. I made the feed handler a C++ application, because I wanted to use C++ standard library.

Second, I added processing of command line arguments (see [binance-feed-handler.cpp:313](https://github.com/featuremine/tutorials/blob/ff04f928715f00fbd06ab0271280519029d4ba78/market-data01-feedhandler/binance-feed-handler.cpp#L313)), so that we can pass a file containing a list of securities and a file to be used by yamal. Here we are using `fmc_cmdline_opt_proc` utility from our Featuremine Common Library `libfmc`, which is also available in the [Yamal repo](https://github.com/featuremine/yamal). Then, I load securities from the file, making sure to eliminate any duplicates first:
```c++
// load securities from the file
vector<string> secs{istream_iterator<string>(secfile), istream_iterator<string>()};
// sort securities
sort(secs.begin(), secs.end());
// remove duplicate securities
auto last = unique(secs.begin(), secs.end());
secs.erase(last, secs.end());
```

Having done that I proceed to open YTP file for reading and writing on line [binance-feed-handler.cpp:351](https://github.com/featuremine/tutorials/blob/ff04f928715f00fbd06ab0271280519029d4ba78/market-data01-feedhandler/binance-feed-handler.cpp#L351) and then create an instance of Yamal as follows:
```c++
mco.yamal = ytp_yamal_new(fd, &error);
if (error) {
    lwsl_err("could not create yamal with error %s\n", fmc_error_msg(error));
    return 1;
}
```

Function [ytp_yamal_new](https://github.com/featuremine/yamal/blob/main/docs/Yamal-C-API.md#ytp_yamal_new) creates an instance of yamal object and I assign yamal instance pointer to the connection context structure, so that is can be easily accessible from the websocket callback when data is received. Notice that we check the `error` pointer to determine whether the error has occurred. This is a pattern used across `libfmc` and `libytp` libraries. This approach standardizes error handling accross the libraries and helps to avoid common error handling bugs when dealing with C libraries.

Yamal is essentially a number of memory mapped linked lists. This structure affords amazing performance without sacrificing flexibility. First list is used for data, while the second list is used for defining logical partition of data into `streams`. `Stream` is defined as a pair of `peer` and `channel`. Think of `peer` as denoting who publishes the data and `channel` as a global namespace or category of the published data. While Yamal refers to the way data is organized into memory mapped lists, Yamal Transport Protocol or `YTP` refers to the protocol that defines how the data is assigned to streams and how streams are announced.

In our case it makes sense to publish each Binance stream to a separate YTP channel. To define streams we need an instance of streams object, which we create as follows:
```c++
auto *streams = ytp_streams_new(mco.yamal, &error);
```
Then in a loop, for each security and type of Bianance feed we need (here `bookTicker` and `trade`), we announce a corresponding YTP stream:
```c++
auto stream = ytp_streams_announce(streams, vpeer.size(), vpeer.data(),
                                    chstr.size(), chstr.data(),
                                    encoding.size(), encoding.data(),
                                    &error);
```
For performance reasons I wanted to use string_view instead of using strings as the c++ unordered_map keep to avoid performing a string copy. This feature now exists in C++20, however, I wanted to keep the code compatible with older standards. For this, I performed a look up of the just defined stream to obtain a persistent string_view from libytp.
```c++
ytp_announcement_lookup(mco.yamal, stream, &seqno, &psz, &peer,
                        &csz, &channel, &esz, &encoding, &original,
                        &subscribed, &error);
mco.streams.emplace(string_view(channel, csz), stream);
```
Finally I added a path variable to the connection context, add the corresponding Binance stream name to the path variable in the loop and change the `i.path` websocket parameter to this built up path:
```c++
i.path = mco->path.c_str();
```
We are almost done. We just need write the data we received from Binance to Yamal. We first isolate the Binance stream name, then the actual update data from the message. Then we look up the corresponding YTP stream and write the data as follows:
```c++
auto dst = ytp_data_reserve(mco->yamal, data.size(), &err);
// ...
memcpy(dst, data.data(), data.size());
ytp_data_commit(mco->yamal, fmc_cur_time_ns(), where->second, dst, &err);
```
Notice that you first reserve the data you need then commit that data to Yamal. Data is not available to anyone else until you commit it and the commit is atomic. This is important because other reader will never see partially written data. At this point we perform a few minor adjustements and improvements and we are done.

## **Validation and Performance**
The moment of truth. We finally get to run our feed handler. I have created two files with (rather short) lists of securities. First, we run one instance of the feed handler.
```bash
./release/market-data01-feedhandler/binance-feed-handler --securities market-data01-feedhandler/securities1.txt --peer feed --ytp-file mktdata.ytp
```
To check content directly we need Yamal tools. For the purpose of this blog, these utilities are build when building tutorial project. To install there utilities normally you can either download one of the [releases](https://github.com/featuremine/yamal/releases) or build from source directly.
Let's first run `yamal-tail` to dump the content of the file to the screen
```bash
./release/dependencies/build/yamal/yamal-tail mktdata.ytp
```
Now we can run another feed handler with the second set of securities.
```bash
./release/market-data01-feedhandler/binance-feed-handler --securities market-data01-feedhandler/securities2.txt --peer feed --ytp-file mktdata.ytp
```
We can run `yamal-stats` to see that the streams corresponding to the second set of securities also appear in yamal.
```bash
./release/dependencies/build/yamal/yamal-stats mktdata.ytp
```
Finally we can run `yamal-local-perf` to monitor performance of yamal bus. This tool listens to the latest messages and displays a histogram of differences between the time on the message and the time the message is received. In our case, since we message time is immediately before committing the message to yamal, difference corresponds to the time it takes to transmit a message over yamal. 
```bash
./release/dependencies/build/yamal/yamal-local-perf mktdata.ytp
```
## **Feeding Data for Trade Plotter**
The last example I would like to discuss in this blog is how to use the market data from yamal. For this purpose I wrote a small Python script that plots a given number of trades together with the corresponding best bid and offer reported at the time of the trade. For convenience we added Python dependencies to **requirements.txt**, you can install them by running
```bash
pip install -r requirements.txt
```
The script takes the yamal file, security to use for the plot and number of trades to show. Here we are using GTK4Cairo backend for matplotlib, but you can use whichever backend you prefer.
```bash
MPLBACKEND=GTK4Cairo python market-data01-feedhandler/binance-view.py --ytp-file mktdata.ytp --security btcusdt --points 1000
```
You should see something like this
![trades](binance-view.png)

The script is well documented and should be easy to follow. Please refer to Yamal documentation for additional information on [Yamal Python API](https://github.com/featuremine/yamal/blob/main/docs/YTP-Python-API.md).

## **Conclusion**
- Combine C++, libwebsockets, and Featuremine Yamal for real-time market data.

## **Feedback**
- Encourage readers to share feedback and experiences.

## **References & Acknowledgements**
- Appreciate libwebsockets and Featuremine Yamal creators.
