# Unlocking Lightning-Speed Market Data | Building a Blazing Fast Binance Feed Server in C++

## **Introduction**

In the realm of financial markets, microseconds, if not nanoseconds, can spell the difference between a successful trade and a missed opportunity. There's no denying the importance of **low-latency and reliable** market data. Trading operations, however, is a large, complex, (often globally) **distributed**, graph of computational processes and most of them require market data in one form or another. Enterprises often have a diverse ecosystem of tools and technologies utilized by these processes and **versatility and interoperability** with meriad of technologies is a key requirements. At the same time, trading is ultimately is a competitive experimental science and ability of the market data platform to **capture** market data and quickly make it available for research and simulations is essential for analysing and responding to latest market conditions.

The multitude of seemingly contrudictory requirements placed on trading technology is what ultimatey makes algorithmic trading such a challenging, yet facinating persuit. Our objective with this series of blogs is to architect a market data platform that meets all four of the requirements mentioned above. In this, first installment, of the series we will focus on building a low-latency Binance Feed Server in C++, we will deploy several of them at once for load balancing, then we will evaluate performance of the feed server, and finally we will implement a simple trade plotter using Python API.

Why is quick market data crucial in trading? Quick responses to market shifts are vital. If a trading strategy lags, the data might be outdated by the time the order reaches the market. Trading based on timely information is super competitive. A strategy that acts fast on profitable trades will benefit. On the flip side, a slow strategy might end up with trades no one else wanted, known as "adverse selection". Delays can result in lost data packets, giving an inaccurate market view. This can also cause data backlogs, especially in strategies where market data processing can't be parallelized. A top-notch market data system uses fewer resources. Think of the huge cost difference between operating five servers versus twenty – it impacts both small groups and big businesses.

## **Why Binance?**
Binance is renowned for its public availability and intuitive API. A plethora of implemented, open-source feed handlers exist for Binance, including those optimized for low latency. Most facets of low-latency and nearly all elements pertinent to distribution and capture are applicable to equity, futures, and FX markets data feeds.

## **Libwebsockets**
[Libwebsockets](https://github.com/warmcat/libwebsockets) stands out as a nimble, pure C library tailored for using contemporary network protocols without a hassle. The library has a minuscule footprint and leverages a non-blocking event loop. Especially for our needs, it's apt for handling a single connection, focusing on the latency of each message. Notably, the library offers a comprehensive example for receiving Binance market data, serving as our foundation.

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
cmake -B release -DCMAKE_BUILD_TYPE=Release ..
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
First, I copied [minimal-ws-client-binance.c](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/minimal-ws-client-binance.c) to [binance-feed-handler.cpp](https://github.com/featuremine/tutorials/blob/main/market-data01-feedhandler/binance-feed-handler.cpp) so that Yamal related changes could be added without interfering with original. I made the feed handler a C++ application, because I wanted to use C++ standard library.

Then as you can see on line [binance-feed-handler.cpp:313](https://github.com/featuremine/tutorials/blob/ff04f928715f00fbd06ab0271280519029d4ba78/market-data01-feedhandler/binance-feed-handler.cpp#L313), I added processing of command line arguments, so that we can pass a file containing a list of securities and a file to be used by yamal. Here we are using a utility from our Featuremine Common Library `libfmc`, which is also available in the [Yamal repo](https://github.com/featuremine/yamal). 
```C
	const char *securities = nullptr;
	const char *peer = nullptr;
	const char *ytpfile = nullptr;
	fmc_cmdline_opt_t options[] = {
		/* 0 */ {"--help", false, NULL},
		/* 1 */ {"--securities", true, &securities},
		/* 2 */ {"--peer", true, &peer},
		/* 3 */ {"--ytp-file", true, &ytpfile},
		{NULL}
	};
	fmc_cmdline_opt_proc(argc, argv, options, &error);
	if (options[0].set) {
		printf("binance-feed-handler --ytp-file FILE --peer PEER --securities SECURITIES\n\n"
			"Binance Feed Server.\n\n"
			"Application will subscribe to quotes and trades streams for the securities provided\n"
			"in the file SECURITIES and will publish each stream onto a separate channel with the\n"
			"same name as the stream. It will publish only the data part of the stream.\n");
		return 0;
	}
	if (error) {
		lwsl_err("%s, could not process args: %s\n", __func__, fmc_error_msg(error));
		return 1;
	}
```

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


------------------------
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