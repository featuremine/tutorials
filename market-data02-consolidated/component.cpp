#include "feed-handler.hpp"
#include "kraken-feed-handler.hpp"

struct fmc_component_def_v1 components[] = {
    {
        .tp_name = "binance_feed_handler",
        .tp_descr = "binance_feed_handler component",
        .tp_size = sizeof(struct binance_feed_handler_component),
        .tp_cfgspec = binance_feed_handler_cfgspec,
        .tp_new = (fmc_newfunc)binance_feed_handler_component_new,
        .tp_del = (fmc_delfunc)binance_feed_handler_component_del,
    },
    {
        .tp_name = "kraken_feed_handler",
        .tp_descr = "kraken_feed_handler component",
        .tp_size = sizeof(struct kraken_feed_handler_component),
        .tp_cfgspec = kraken_feed_handler_cfgspec,
        .tp_new = (fmc_newfunc)kraken_feed_handler_component_new,
        .tp_del = (fmc_delfunc)kraken_feed_handler_component_del,
    },
    {NULL},
};

#ifdef __cplusplus
extern "C" {
#endif

FMCOMPMODINITFUNC void FMCompInit_feed_handler(struct fmc_component_api *api,
                                               struct fmc_component_module *mod) {
  api->components_add_v1(mod, components);
  _reactor = api->reactor_v1;
}

#ifdef __cplusplus
}
#endif