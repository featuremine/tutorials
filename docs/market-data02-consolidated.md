# Harnessing Rapid Market Data Part 2: Redundancy and Normalization

## **Constructing the Consolidating Feed Parser**

### **Getting Started**

To facilitate this tutorial, we've created a repository containing all of the relevant code. Before diving in, ensure you've installed [git](https://git-scm.com/downloads), [CMake](https://cmake.org/download), C++ compiler toolchain and set up your favorite development environment. For example, [here](https://code.visualstudio.com/docs/languages/cpp) is the reference on how to set up Visual Studio Code. This project is compatible with contemporary Linux and MacOS setups. For Windows users, consider using either the Windows Subsystem for Linux (WSL) or a Docker container.

Kick off by cloning the tutorial repository, setting up the build directory and running the build:
```bash
git clone --recurse-submodules https://github.com/featuremine/tutorials
cd tutorials
cmake -B release -DCMAKE_BUILD_TYPE=Release
cmake --build release
```
Post-build, you should be able to find the tutorial binaries under **release/market-data02-consolidated**. All of the relevant sources are in the **market-data02-consolidated** directory of the repository.

### **Validating and Assessing Performance**

Now, it’s time to test our feed handler in action. For this exercise, we’ve prepared two configuration files, each containing a curated list of securities. To start, run one feed handler instance:
```bash
YAMALCOMPPATH=./release/dependencies/build/yamal/package/lib/yamal/modules ./release/dependencies/build/yamal/package/bin/yamal-run -c market-data02-consolidated/feed-handler-one.json --json
```
To check content directly, we need Yamal tools. For this blog, these utilities are built together with a tutorial project. To install these utilities normally you can either download one of the [releases](https://github.com/featuremine/yamal/releases) or build from source directly. Let's first run `yamal-tail` to dump the content of the file to the screen
```bash
./release/dependencies/build/yamal/package/bin/yamal-tail -f mktdata.ytp
```
Now, we can run another feed handler with the second set of configurations.
```bash
YAMALCOMPPATH=./release/dependencies/build/yamal/package/lib/yamal/modules ./release/dependencies/build/yamal/package/bin/yamal-run -c market-data02-consolidated/feed-handler-two.json --json
```
We can run `yamal-stats` to see that the streams corresponding to the second configuration also appear in Yamal.
```bash
./release/dependencies/build/yamal/package/bin/yamal-stats mktdata.ytp
```
Then we run the consolidating feed parser.
```bash
YAMALCOMPPATH=./release/dependencies/build/yamal/package/lib/yamal/modules ./release/dependencies/build/yamal/package/bin/yamal-run -c market-data02-consolidated/feed-parser.json --json
```
It arbitrates between multiple feeds and normalizes the data. Notice the extension of the output file in the feed parser configuration is **ytp.0001**. This is important because we will later introduce file rollover, where data will be split among multiple files.

You can dump market data to the terminal using the following script:
```bash
python3 market-data02-consolidated/ore-dump.py --follow=true --ytp-file consolidated.ytp.0001
```

To display the data you can use **trade_view** script:
```bash
python3 market-data02-consolidated/trade-view.py --ytp-file consolidated.ytp --security btcusdt --market binance --points 20
```