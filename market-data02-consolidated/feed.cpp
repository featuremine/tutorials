/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.

 *****************************************************************************/

#include <fmc/component.h>

struct fmc_reactor_api_v1 *_reactor;

struct binance_feed_handler_component *
binance_feed_handler_component_new(struct fmc_cfg_sect_item *cfg,
                                   struct fmc_reactor_ctx *ctx,
                                   char **inp_tps) noexcept;

void binance_feed_handler_component_del(
    struct binance_feed_handler_component *comp) noexcept;

extern struct fmc_cfg_node_spec *binance_feed_handler_cfg;

extern size_t binance_feed_handler_struct_sz;

struct kraken_feed_handler_component *
kraken_feed_handler_component_new(struct fmc_cfg_sect_item *cfg,
                                  struct fmc_reactor_ctx *ctx,
                                  char **inp_tps) noexcept;

void kraken_feed_handler_component_del(
    struct kraken_feed_handler_component *comp) noexcept;

extern struct fmc_cfg_node_spec *kraken_feed_handler_cfg;

extern size_t kraken_feed_handler_struct_sz;

struct runner_t *
feed_parser_component_new(struct fmc_cfg_sect_item *cfg,
                                  struct fmc_reactor_ctx *ctx,
                                  char **inp_tps) noexcept;

void feed_parser_component_del(
    struct runner_t *comp) noexcept;

extern struct fmc_cfg_node_spec *feed_parser_cfg;

extern size_t feed_parser_struct_sz;

struct fmc_component_def_v1 components[] = {
    {
        .tp_name = "binance-feed-handler",
        .tp_descr = "Binance feed handler component",
        .tp_size = binance_feed_handler_struct_sz,
        .tp_cfgspec = binance_feed_handler_cfg,
        .tp_new = (fmc_newfunc)binance_feed_handler_component_new,
        .tp_del = (fmc_delfunc)binance_feed_handler_component_del,
    },
    {
        .tp_name = "kraken-feed-handler",
        .tp_descr = "Kraken feed handler component",
        .tp_size = kraken_feed_handler_struct_sz,
        .tp_cfgspec = kraken_feed_handler_cfg,
        .tp_new = (fmc_newfunc)kraken_feed_handler_component_new,
        .tp_del = (fmc_delfunc)kraken_feed_handler_component_del,
    },
    {
        .tp_name = "feed-parser",
        .tp_descr = "Feed parser component",
        .tp_size = feed_parser_struct_sz,
        .tp_cfgspec = feed_parser_cfg,
        .tp_new = (fmc_newfunc)feed_parser_component_new,
        .tp_del = (fmc_delfunc)feed_parser_component_del,
    },
    {NULL},
};

#ifdef __cplusplus
extern "C" {
#endif

FMCOMPMODINITFUNC void
FMCompInit_feed(struct fmc_component_api *api,
                        struct fmc_component_module *mod) {
  api->components_add_v1(mod, components);
  _reactor = api->reactor_v1;
}

#ifdef __cplusplus
}
#endif
