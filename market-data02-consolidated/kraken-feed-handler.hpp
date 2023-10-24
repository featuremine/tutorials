/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.

 *****************************************************************************/

#include <ctype.h>
#include <libwebsockets.h>
#include <signal.h>
#include <string.h>

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <fmc/alignment.h>
#include <fmc/component.h>
#include <fmc/files.h>
#include <fmc/time.h>
#include <fmc/config.h>
#include <fmc++/mpl.hpp>
#include <ytp/announcement.h>
#include <ytp/data.h>
#include <ytp/streams.h>
#include <ytp/yamal.h>

namespace std {
template <> struct hash<std::pair<std::string_view, std::string_view>> {
  hash() = default;
  using argument_type = std::pair<std::string_view, std::string_view>;
  using result_type = std::size_t;
  result_type operator()(argument_type const &obj) const {
    return fmc_hash_combine(std::hash<std::string_view>{}(std::get<0>(obj)),
                            std::hash<std::string_view>{}(std::get<1>(obj)));
  }
};
} // namespace std

namespace kraken {

typedef struct range {
  unsigned int samples;
} stats_t;

/*
 * This represents your object that "contains" the client connection and has
 * the client connection bound to it
 */

static struct mco {
  lws_sorted_usec_list_t sul;    /* schedule connection retry */
  lws_sorted_usec_list_t sul_hz; /* 1hz summary */

  stats_t stats;

  struct lws *wsi;      /* related wsi if any */
  uint16_t retry_count; /* count of consequetive retries */

  std::unordered_map<std::pair<std::string_view, std::string_view>,
                     ytp_mmnode_offs>
      streams;
  ytp_yamal_t *yamal = nullptr;
  std::string tickers; /* storing the tickers for stream subscription */
} mco;

static struct fmc_reactor_api_v1 *_reactor;
static struct lws_context *context;
static int interrupted;
static const char *address = "ws.kraken.com";
static int port = 443;

#if defined(LWS_WITH_MBEDTLS) || defined(USE_WOLFSSL)
/*
 * OpenSSL uses the system trust store.  mbedTLS / WolfSSL have to be told which
 * CA to trust explicitly.
 */
static const char *const ca_pem_digicert_global_root =
    "-----BEGIN CERTIFICATE-----\n"
    "MIIDrzCCApegAwIBAgIQCDvgVpBCRrGhdWrJWZHHSjANBgkqhkiG9w0BAQUFADBh\n"
    "MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3\n"
    "d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBD\n"
    "QTAeFw0wNjExMTAwMDAwMDBaFw0zMTExMTAwMDAwMDBaMGExCzAJBgNVBAYTAlVT\n"
    "MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j\n"
    "b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IENBMIIBIjANBgkqhkiG\n"
    "9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4jvhEXLeqKTTo1eqUKKPC3eQyaKl7hLOllsB\n"
    "CSDMAZOnTjC3U/dDxGkAV53ijSLdhwZAAIEJzs4bg7/fzTtxRuLWZscFs3YnFo97\n"
    "nh6Vfe63SKMI2tavegw5BmV/Sl0fvBf4q77uKNd0f3p4mVmFaG5cIzJLv07A6Fpt\n"
    "43C/dxC//AH2hdmoRBBYMql1GNXRor5H4idq9Joz+EkIYIvUX7Q6hL+hqkpMfT7P\n"
    "T19sdl6gSzeRntwi5m3OFBqOasv+zbMUZBfHWymeMr/y7vrTC0LUq7dBMtoM1O/4\n"
    "gdW7jVg/tRvoSSiicNoxBN33shbyTApOB6jtSj1etX+jkMOvJwIDAQABo2MwYTAO\n"
    "BgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUA95QNVbR\n"
    "TLtm8KPiGxvDl7I90VUwHwYDVR0jBBgwFoAUA95QNVbRTLtm8KPiGxvDl7I90VUw\n"
    "DQYJKoZIhvcNAQEFBQADggEBAMucN6pIExIK+t1EnE9SsPTfrgT1eXkIoyQY/Esr\n"
    "hMAtudXH/vTBH1jLuG2cenTnmCmrEbXjcKChzUyImZOMkXDiqw8cvpOp/2PV5Adg\n"
    "06O/nVsJ8dWO41P0jmP6P6fbtGbfYmbW0W5BjfIttep3Sp+dWOIrWcBAI+0tKIJF\n"
    "PnlUkiaY4IBIqDfv8NZ5YBberOgOzW6sRBc4L0na4UU+Krk2U886UAb3LujEV0ls\n"
    "YSEY1QSteDwsOoBrp+uvFRTp2InBuThs4pFsiv9kuXclVzDAGySj4dzp30d8tbQk\n"
    "CAUw7C29C79Fv1C5qfPrmAESrciIxpg0X40KPMbp1ZWVbd4=\n"
    "-----END CERTIFICATE-----\n";
#endif

/*
 * The retry and backoff policy we want to use for our client connections
 */

static const uint32_t backoff_ms[] = {1000, 2000, 3000, 4000, 5000};

static const lws_retry_bo_t retry = {
    .retry_ms_table = backoff_ms,
    .retry_ms_table_count = LWS_ARRAY_SIZE(backoff_ms),
    .conceal_count = LWS_ARRAY_SIZE(backoff_ms),

    .secs_since_valid_ping = 0,   /* force PINGs after secs idle */
    .secs_since_valid_hangup = 0, /* hangup after secs idle */

    .jitter_percent = 0,
};

/*
 * If we don't enable permessage-deflate ws extension, during times when there
 * are many ws messages per second the server coalesces them inside a smaller
 * number of larger ssl records, for >100 mps typically >2048 records.
 *
 * This is a problem, because the coalesced record cannot be send nor decrypted
 * until the last part of the record is received, meaning additional latency
 * for the earlier members of the coalesced record that have just been sitting
 * there waiting for the last one to go out and be decrypted.
 *
 * permessage-deflate reduces the data size before the tls layer, for >100mps
 * reducing the colesced records to ~1.2KB.
 */

static const struct lws_extension extensions[] = {
    {"permessage-deflate", lws_extension_callback_pm_deflate,
     "permessage-deflate"
     "; client_no_context_takeover"
     "; client_max_window_bits"},
    {NULL, NULL, NULL /* terminator */}};
/*
 * Scheduled sul callback that starts the connection attempt
 */

static void connect_client(lws_sorted_usec_list_t *sul) {
  struct mco *mco = lws_container_of(sul, struct mco, sul);
  struct lws_client_connect_info i;

  memset(&i, 0, sizeof(i));

  i.context = context;
  i.port = port;
  i.address = address;
  i.host = i.address;
  i.origin = i.address;
  i.ssl_connection = LCCSCF_USE_SSL | LCCSCF_PRIORITIZE_READS;
  i.protocol = NULL;
  i.local_protocol_name = "lws-minimal-client";
  i.pwsi = &mco->wsi;
  i.retry_and_idle_policy = &retry;
  i.userdata = mco;

  if (!lws_client_connect_via_info(&i))
    /*
     * Failed... schedule a retry... we can't use the _retry_wsi()
     * convenience wrapper api here because no valid wsi at this
     * point.
     */
    if (lws_retry_sul_schedule(context, 0, sul, &retry, connect_client,
                               &mco->retry_count)) {
      lwsl_err("%s: connection attempts exhausted\n", __func__);
      interrupted = 1;
    }
}

static void stats_reset(stats_t *r) { r->samples = 0; }

static void sul_hz_cb(lws_sorted_usec_list_t *sul) {
  struct mco *mco = lws_container_of(sul, struct mco, sul_hz);

  /*
   * We are called once a second to dump statistics on the connection
   */

  lws_sul_schedule(lws_get_context(mco->wsi), 0, &mco->sul_hz, sul_hz_cb,
                   LWS_US_PER_SEC);

  lwsl_notice("%s: %d msg/s\n", __func__, mco->stats.samples);

  stats_reset(&mco->stats);
}

static int callback_minimal(struct lws *wsi, enum lws_callback_reasons reason,
                            void *user, void *in, size_t len) {
  using namespace std;
  struct mco *mco = (struct mco *)user;
  const char *p = nullptr;
  size_t alen = 0;
  fmc_error_t *err = nullptr;
  string_view channelName;
  string_view pairName;
  string_view data;
  string_view::size_type offset1, offset2;

  switch (reason) {

  case LWS_CALLBACK_CLIENT_CONNECTION_ERROR:
    lwsl_err("CLIENT_CONNECTION_ERROR: %s\n", in ? (char *)in : "(null)");
    goto do_retry;
    break;

  case LWS_CALLBACK_CLIENT_RECEIVE:
    data = std::string_view((const char *)in, len);
    if (data[0] == '{') {
      p = lws_json_simple_find((const char *)in, len, "\"event\"", &alen);
      if (!p) {
        lwsl_err("%s, message does not contain \"event\":\n", __func__);
        break;
      }
      std::string_view event = std::string_view((const char *)p + 2, alen - 3);
      if (event == "heratbeat") {
        break;
      } else if (event == "subscriptionStatus") {
        p = lws_json_simple_find((const char *)in, len, "\"status\"", &alen);
        if (!p) {
          lwsl_err("%s, message does not contain \"status\":\n", __func__);
          break;
        }
        std::string_view status =
            std::string_view((const char *)p + 2, alen - 3);
        if (status != "subscribed") {
          lwsl_err("%s, unable to complete subscription, \"status\" value is "
                   "%.*s:\n",
                   __func__, static_cast<int>(status.size()), status.data());
          interrupted = 1;
          break;
        }
      } else if (event == "systemStatus") {
        p = lws_json_simple_find((const char *)in, len, "\"status\"", &alen);
        if (!p) {
          lwsl_err("%s, message does not contain \"status\":\n", __func__);
          break;
        }
        std::string_view status =
            std::string_view((const char *)p + 2, alen - 3);
        if (status != "online") {
          lwsl_err("%s, unable to complete subscription, \"status\" value is "
                   "%.*s:\n",
                   __func__, static_cast<int>(status.size()), status.data());
          interrupted = 1;
          break;
        }
      } else {
        // Unexpected message
      }
      break;
    }
    offset2 = data.rfind("\"");
    if (offset2 == std::string_view::npos) {
      lwsl_err("%s, could not find expected quote character in message, "
               "invalid data received \"%.*s\":\n",
               __func__, static_cast<int>(data.size()), data.data());
      break;
    }
    offset1 = data.rfind("\"", offset2 - 1);
    if (offset1 == std::string_view::npos) {
      lwsl_err("%s, could not find expected quote character in message, "
               "invalid data received \"%.*s\":\n",
               __func__, static_cast<int>(data.size()), data.data());
      break;
    }
    channelName = data.substr(offset1 + 1, offset2 - offset1 - 1);
    offset2 = data.rfind("\"", offset1 - 1);
    if (offset2 == std::string_view::npos) {
      lwsl_err("%s, could not find expected quote character in message, "
               "invalid data received \"%.*s\":\n",
               __func__, static_cast<int>(data.size()), data.data());
      break;
    }
    offset1 = data.rfind("\"", offset2 - 1);
    if (offset1 == std::string_view::npos) {
      lwsl_err("%s, could not find expected quote character in message, "
               "invalid data received \"%.*s\":\n",
               __func__, static_cast<int>(data.size()), data.data());
      break;
    }
    pairName = data.substr(offset1 + 1, offset2 - offset1 - 1);
    if (auto where =
            mco->streams.find(std::pair<std::string_view, std::string_view>(
                channelName, pairName));
        where != mco->streams.end()) {
      auto dst = ytp_data_reserve(mco->yamal, data.size(), &err);
      if (err) {
        lwsl_err("%s, could not reserve yamal message with error %s:\n",
                 __func__, fmc_error_msg(err));
        break;
      }
      memcpy(dst, data.data(), data.size());
      ytp_data_commit(mco->yamal, fmc_cur_time_ns(), where->second, dst, &err);
      if (err) {
        lwsl_err("%s, could not commit with error %s:\n", __func__,
                 fmc_error_msg(err));
        break;
      }
    } else {
      lwsl_err(
          "%s, stream map does not contain %s, %s. Message received %.*s:\n",
          __func__, string(channelName).c_str(), string(pairName).c_str(),
          static_cast<int>(data.size()), data.data());
      break;
    }
    mco->stats.samples++;
    break;
  case LWS_CALLBACK_CLIENT_ESTABLISHED: {
    lwsl_user("%s: established\n", __func__);
    lws_sul_schedule(lws_get_context(wsi), 0, &mco->sul_hz, sul_hz_cb,
                     LWS_US_PER_SEC);
    mco->wsi = wsi;
    stats_reset(&mco->stats);
    std::string subscription = std::string(LWS_SEND_BUFFER_PRE_PADDING, '\0') +
                               "{\"event\":\"subscribe\",\"pair\":[" +
                               mco->tickers +
                               "],\"subscription\":{\"name\":\"spread\"}}" +
                               std::string(LWS_SEND_BUFFER_POST_PADDING, '\0');
    auto wret = lws_write(mco->wsi,
                          (unsigned char *)subscription.data() +
                              LWS_SEND_BUFFER_PRE_PADDING,
                          subscription.size() - LWS_SEND_BUFFER_PRE_PADDING -
                              LWS_SEND_BUFFER_POST_PADDING,
                          LWS_WRITE_TEXT);
    if (wret == -1) {
      lwsl_err("%s: unable to write subscription message\n", __func__);
      interrupted = 1;
      break;
    }
    subscription = std::string(LWS_SEND_BUFFER_PRE_PADDING, '\0') +
                   "{\"event\":\"subscribe\",\"pair\":[" + mco->tickers +
                   "],\"subscription\":{\"name\":\"trade\"}}" +
                   std::string(LWS_SEND_BUFFER_POST_PADDING, '\0');
    wret = lws_write(mco->wsi,
                     (unsigned char *)subscription.data() +
                         LWS_SEND_BUFFER_PRE_PADDING,
                     subscription.size() - LWS_SEND_BUFFER_PRE_PADDING -
                         LWS_SEND_BUFFER_POST_PADDING,
                     LWS_WRITE_TEXT);
    if (wret == -1) {
      lwsl_err("%s: unable to write subscription message\n", __func__);
      interrupted = 1;
      break;
    }
    break;
  }
  case LWS_CALLBACK_CLIENT_CLOSED:
    lws_sul_cancel(&mco->sul_hz);
    goto do_retry;

  default:
    break;
  }

  return lws_callback_http_dummy(wsi, reason, user, in, len);

do_retry:
  /*
   * retry the connection to keep it nailed up
   *
   * For this example, we try to conceal any problem for one set of
   * backoff retries and then exit the app.
   *
   * If you set retry.conceal_count to be LWS_RETRY_CONCEAL_ALWAYS,
   * it will never give up and keep retrying at the last backoff
   * delay plus the random jitter amount.
   */
  if (lws_retry_sul_schedule_retry_wsi(wsi, &mco->sul, connect_client,
                                       &mco->retry_count)) {
    lwsl_err("%s: connection attempts exhausted\n", __func__);
    interrupted = 1;
  }

  return 0;
}

static const struct lws_protocols protocols[] = {
    {"lws-minimal-client", callback_minimal, 0, 0, 0, NULL, 0},
    LWS_PROTOCOL_LIST_TERM};

struct feed_handler_component {
    fmc_component_HEAD;

    feed_handler_component(struct fmc_cfg_sect_item *cfg) {
        using namespace std;

        fmc_fd fd;
        fmc_error_t *error = nullptr;

        struct lws_context_creation_info info;
        memset(&info, 0, sizeof info);

        lwsl_user("kraken feed handler\n");

        info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;
        info.port = CONTEXT_PORT_NO_LISTEN; /* we do not run any server */
        info.protocols = protocols;
        info.fd_limit_per_thread = 1 + 1 + 1;
        info.extensions = extensions;

        ifstream secfile{fmc_cfg_sect_item_get(cfg, "securities")->node.value.str};
        if (!secfile) {
            lwsl_err("%s: failed to open securities file %s\n", __func__, fmc_cfg_sect_item_get(cfg, "securities")->node.value.str);
            fmc_runtime_error_unless(false) << __func__ << ": failed to open securities file "<<fmc_cfg_sect_item_get(cfg, "securities")->node.value.str;
        }

        // load securities from the file
        vector<string> secs{istream_iterator<string>(secfile),
                            istream_iterator<string>()};
        // sort securities
        sort(secs.begin(), secs.end());
        // remove duplicate securities
        auto last = unique(secs.begin(), secs.end());
        secs.erase(last, secs.end());

        fd = fmc_fopen(fmc_cfg_sect_item_get(cfg, "ytp-file")->node.value.str, fmc_fmode::READWRITE, &error);
        if (error) {
            lwsl_err("could not open file %s with error %s\n", fmc_cfg_sect_item_get(cfg, "ytp-file")->node.value.str,
                    fmc_error_msg(error));
            fmc_runtime_error_unless(false) << "could not open file "<<fmc_cfg_sect_item_get(cfg, "ytp-file")->node.value.str<<" with error "<<fmc_error_msg(error);
        }
        mco.yamal = ytp_yamal_new(fd, &error);
        if (error) {
            lwsl_err("could not create yamal with error %s\n", fmc_error_msg(error));
            fmc_runtime_error_unless(false) << "could not create yamal with error "<<fmc_error_msg(error);
        }
        streams = ytp_streams_new(mco.yamal, &error);
        if (error) {
            lwsl_err("could not create stream with error %s\n", fmc_error_msg(error));
            fmc_runtime_error_unless(false) << "could not create stream with error "<<fmc_error_msg(error);
        }

        string_view vpeer(fmc_cfg_sect_item_get(cfg, "peer")->node.value.str);
        string encoding = "Content-Type application/json\n"
                            "Content-Schema Kraken";
        vector<string> types = {"spread", "trade"};
        ostringstream ss;
        bool first = true;
        ss << "/stream?streams=";
        constexpr string_view prefix = "raw/kraken/";
        for (auto &&sec : secs) {
            for (auto &&tp : types) {
                string chstr = string(prefix) + sec + "@" + tp;
                auto stream = ytp_streams_announce(
                    streams, vpeer.size(), vpeer.data(), chstr.size(), chstr.data(),
                    encoding.size(), encoding.data(), &error);
                uint64_t seqno;
                size_t psz;
                const char *peer;
                size_t csz;
                const char *channel;
                size_t esz;
                const char *encoding;
                ytp_mmnode_offs *original;
                ytp_mmnode_offs *subscribed;

                ytp_announcement_lookup(mco.yamal, stream, &seqno, &psz, &peer, &csz,
                                        &channel, &esz, &encoding, &original, &subscribed,
                                        &error);
                mco.streams.emplace(
                   std::pair<std::string_view, std::string_view>(sec, tp), stream);
            }
            ss << (first ? "" : ",") << "\"" << sec << "\"";
            first = false;
        }
        mco.tickers = ss.str();

        #if defined(LWS_WITH_MBEDTLS) || defined(USE_WOLFSSL)
        /*
        * OpenSSL uses the system trust store.  mbedTLS / WolfSSL have to be
        * told which CA to trust explicitly.
        */
        info.client_ssl_ca_mem = ca_pem_digicert_global_root;
        info.client_ssl_ca_mem_len =
            (unsigned int)strlen(ca_pem_digicert_global_root);
        #endif

        context = lws_create_context(&info);
        if (!context) {
            lwsl_err("lws init failed\n");
            fmc_runtime_error_unless(false) << "lws init failed";
        }

        /* schedule the first client connection attempt to happen immediately */
        lws_sul_schedule(context, 0, &mco.sul, connect_client, 1);
    }
    bool process_one() {
        return !interrupted && lws_service(context, 0) >= 0;
    }
    ~feed_handler_component() {
        lws_context_destroy(context);

        fmc_error_t *error = nullptr;
        ytp_streams_del(streams, &error);
        ytp_yamal_del(mco.yamal, &error);

        lwsl_user("Completed\n");
    }
    ytp_streams_t *streams = nullptr;
};

} // namespace kraken

static void kraken_feed_handler_component_del(struct kraken::feed_handler_component *comp) noexcept {
  delete comp;
}

static void kraken_feed_handler_component_process_one(struct fmc_component *self,
                                       struct fmc_reactor_ctx *ctx,
                                       fmc_time64_t now) noexcept {
  struct kraken::feed_handler_component *comp = (kraken::feed_handler_component *)self;
  try {
    if (comp->process_one())
        _reactor->queue(ctx);
  } catch (std::exception &e) {
    _reactor->set_error(ctx, "%s", e.what());
  }
}

static struct kraken::feed_handler_component *kraken_feed_handler_component_new(struct fmc_cfg_sect_item *cfg,
                                                 struct fmc_reactor_ctx *ctx,
                                                 char **inp_tps) noexcept {
  struct kraken::feed_handler_component *comp = nullptr;
  try {
    comp = new struct kraken::feed_handler_component(cfg);
    _reactor->on_exec(ctx, kraken_feed_handler_component_process_one);
    _reactor->queue(ctx);
  } catch (std::exception &e) {
    _reactor->set_error(ctx, "%s", e.what());
  }
  return comp;
}

struct fmc_cfg_node_spec kraken_feed_handler_cfgspec[] = {
    {.key = "securities",
     .descr = "securities file path",
     .required = true,
     .type =
         {
             .type = FMC_CFG_STR,
         }},
    {.key = "peer",
     .descr = "Kraken feed handler peer name",
     .required = true,
     .type =
         {
             .type = FMC_CFG_STR,
         }},
    {.key = "ytp-file",
     .descr = "Kraken feed handler ytp-file name",
     .required = true,
     .type =
         {
             .type = FMC_CFG_STR,
         }},
    {NULL},
};
