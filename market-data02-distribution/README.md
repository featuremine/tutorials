## Why low-latency market data is so important in trading?
- **Relevance**: The more time a strategy takes to respond to market events, the less relevant the information will be by the time the order gets to the market.
- **Competition**: Acting upon information available to multiple participants is fiercely competitive.
- **Profitable Decisions**: A strategy that can promptly capitalize on a trade expected to yield profit will earn money.
- **Adverse Selection**: Conversely, if a strategy is too slow, it's likely making an undesirable trade that no one else sought—this is referred to as "adverse selection".
- **Data Integrity**: Slow processing can lead to packet loss and consequently, flawed market data. It can also cause exponential queuing, leading to substantially delayed data, particularly for cross-sectional strategies where parallelization isn’t feasible.
- **Resource Efficiency**: A high-performance market data platform demands fewer resources. The cost difference between running five servers or twenty can be monumental, affecting both small teams and large enterprises.

## Easy and availability of distribution is another requirement for market data platforms:
- **Versatility**: Making market data available to diverse strategies, signal servers, and monitoring tools is vital.
- **Dual Needs**: Both low-latency and a broad spectrum of destinations are crucial.
- **Requirements**: While a fast signal server might mandate low-latency distribution, an enterprise risk monitor could leverage a kafka-based feed.
- **Interoperability**: The IT department has it easier when various programming languages and tools can readily access the market data.
- **Expandability**: It should be straightforward to devise new tools and adapters to access or disseminate the market data.
- **Performance Independence**: Different market data routes must not impair each other's efficiency.

## Capture is another important aspect of the market data platform:
- **Data Reservoir**: It's crucial to have several hours of market data available for strategies to initialize their state upon launch.
- **Research and Analysis**: Near real-time processing of market data is pivotal for evaluation, research, and subsequent data archiving to facilitate further studies and simulations.
- **Near real-time archive**: Ability to archive market data nearly real-time, allows research teams to analyse startegy performance and to make model adjustments for the following trading day.
