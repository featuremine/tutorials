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

#include <fmc/cmdline.h>
#include <fmc/files.h>
#include <fmc/time.h>
#include <ytp/announcement.h>
#include <ytp/data.h>
#include <ytp/streams.h>
#include <ytp/yamal.h>

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

  std::unordered_map<std::string_view, ytp_mmnode_offs> streams;
  ytp_yamal_t *yamal = nullptr;
  std::string path; /* storing the path for stream subscription */
  std::string subscription;
  std::string apikey;
  std::string secret;
  std::string passphrase;
} mco;

static struct lws_context *context;
static int interrupted;
static const char *address = "ws-direct.exchange.coinbase.com";
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
  i.path = mco->path.c_str();
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
  string_view stream;
  string_view data;

  switch (reason) {

  case LWS_CALLBACK_CLIENT_CONNECTION_ERROR:
    lwsl_err("CLIENT_CONNECTION_ERROR: %s\n", in ? (char *)in : "(null)");
    goto do_retry;
    break;

  case LWS_CALLBACK_CLIENT_RECEIVE:
    //TODO: Validate subscriptions message as a response
    p = lws_json_simple_find((const char *)in, len, "\"product_id\"", &alen);
    if (!p) {
      lwsl_err("%s, message does not contain \"product_id\":\n", __func__);
      break;
    }
    stream = std::string_view((const char *)p + 2, alen - 3);
    data = std::string_view((const char *)in, len);
    if (auto where = mco->streams.find(stream); where != mco->streams.end()) {
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
      lwsl_err("%s, stream map does not contain %s:\n", __func__,
               string(stream).c_str());
      break;
    }
    mco->stats.samples++;
    break;
  case LWS_CALLBACK_CLIENT_ESTABLISHED:
    lwsl_user("%s: established\n", __func__);
    lws_sul_schedule(lws_get_context(wsi), 0, &mco->sul_hz, sul_hz_cb,
                     LWS_US_PER_SEC);
    mco->wsi = wsi;
    stats_reset(&mco->stats);
    //TODO: Check for error on write
    lws_write(mco->wsi, (unsigned char *) mco->subscription.data() + LWS_SEND_BUFFER_PRE_PADDING,
              mco->subscription.size() - LWS_SEND_BUFFER_PRE_PADDING - LWS_SEND_BUFFER_POST_PADDING,
              LWS_WRITE_TEXT);
    break;

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

static void sigint_handler(int sig) { interrupted = 1; }

static void hmac_sha256(unsigned char *digest, std::string_view key,
                        std::string_view msg) {
  unsigned int len = SHA256_DIGEST_LENGTH;
#if OPENSSL_VERSION_NUMBER < 0x10100000L
  HMAC_CTX hmac;
  HMAC_CTX_init(&hmac);
  HMAC_Init_ex(&hmac, key.data(), key.length(), EVP_sha256(), NULL);
  HMAC_Update(&hmac, (const unsigned char *)msg.data(), msg.length());
  HMAC_Final(&hmac, digest, &len);
  HMAC_CTX_cleanup(&hmac);
#elif OPENSSL_VERSION_NUMBER < 0x30000000L
  auto hmac = HMAC_CTX_new();
  HMAC_Init_ex(hmac, key.data(), key.length(), EVP_sha256(), NULL);
  HMAC_Update(hmac, (const unsigned char *)msg.data(), msg.length());
  HMAC_Final(hmac, digest, &len);
  HMAC_CTX_free(hmac);
#else
  HMAC(EVP_sha256(), key.data(), key.length(), (unsigned char *)msg.data(),
       msg.length(), digest, &len);
#endif
}

inline std::string base64_encode(const unsigned char *input, size_t length) {
  const unsigned int pl = 4 * ((length + 2) / 3);
  std::string output(pl, 0);
  const unsigned int ol =
      EVP_EncodeBlock((unsigned char *)output.data(), input, length);
  if (pl != ol) {
    std::cerr << "Encode predicted " << pl << " but we got " << ol << "\n";
  }
  return output;
}

inline std::string base64_decode(const char *input, int length) {

  BIO *b64, *bmem;
  std::string buffer(length, 0);
  b64 = BIO_new(BIO_f_base64());
  BIO_set_flags(b64, BIO_FLAGS_BASE64_NO_NL);
  bmem = BIO_new_mem_buf(input, -1);
  bmem = BIO_push(b64, bmem);
  const int maxlen = strlen(input) / 4 * 3 + 1;
  const int len = BIO_read(bmem, buffer.data(), maxlen);
  BIO_free_all(bmem);
  buffer.resize(len);
  return buffer;
}

inline std::string hmac_base64(std::string_view key, std::string_view msg) {
  unsigned char hash[SHA256_DIGEST_LENGTH];
  unsigned int len = SHA256_DIGEST_LENGTH;
  hmac_sha256(hash, key, msg);

  std::stringstream ss;
  ss << std::setfill('0');
  for (unsigned int i = 0; i < len; i++) {
    ss << hash[i];
  }
  return base64_encode((unsigned char *)ss.str().c_str(), len);
}

int main(int argc, const char **argv) {
  using namespace std;

  struct lws_context_creation_info info;
  fmc_fd fd;
  fmc_error_t *error = nullptr;

  signal(SIGINT, sigint_handler);
  memset(&info, 0, sizeof info);
  lws_cmdline_option_handle_builtin(argc, argv, &info);

  lwsl_user("coinbase feed handler\n");

  info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;
  info.port = CONTEXT_PORT_NO_LISTEN; /* we do not run any server */
  info.protocols = protocols;
  info.fd_limit_per_thread = 1 + 1 + 1;
  info.extensions = extensions;

  const char *securities = nullptr;
  const char *peer = nullptr;
  const char *ytpfile = nullptr;
  const char *apikey = nullptr;
  const char *secret = nullptr;
  const char *password = nullptr;
  fmc_cmdline_opt_t options[] = {/* 0 */ {"--help", false, NULL},
                                 /* 1 */ {"--securities", true, &securities},
                                 /* 2 */ {"--peer", true, &peer},
                                 /* 3 */ {"--ytp-file", true, &ytpfile},
                                 /* 4 */ {"--api-key", false, &apikey},
                                 /* 5 */ {"--secret", false, &secret},
                                 /* 6 */ {"--password", false, &password},
                                 /* 7 */ {"--public", false, NULL},
                                 /* 7 */ {"--batch", false, NULL},
                                 {NULL}};
  fmc_cmdline_opt_proc(argc, argv, options, &error);
  if (options[0].set) {
    printf("coinbase-feed-handler --ytp-file FILE --peer PEER --securities "
           "SECURITIES\n\n"
           "Coinbase Feed Server.\n\n"
           "Application will subscribe to quotes and trades streams for the "
           "securities provided\n"
           "in the file SECURITIES and will publish each stream onto a "
           "separate channel with the\n"
           "same name as the stream. It will publish only the data part of the "
           "stream.\n");
    return 0;
  }
  if (error) {
    lwsl_err("%s, could not process args: %s\n", __func__,
             fmc_error_msg(error));
    return 1;
  }

  mco.apikey = apikey;
  mco.secret = secret;
  mco.passphrase = password;

  if (options[7].set) {
    address = "ws-feed.exchange.coinbase.com";
    port = 443;
  }

  ifstream secfile{securities};
  if (!secfile) {
    lwsl_err("%s: failed to open securities file %s\n", __func__, securities);
    return 1;
  }

  // load securities from the file
  vector<string> secs{istream_iterator<string>(secfile),
                      istream_iterator<string>()};
  // sort securities
  sort(secs.begin(), secs.end());
  // remove duplicate securities
  auto last = unique(secs.begin(), secs.end());
  secs.erase(last, secs.end());

  fd = fmc_fopen(ytpfile, fmc_fmode::READWRITE, &error);
  if (error) {
    lwsl_err("could not open file %s with error %s\n", ytpfile,
             fmc_error_msg(error));
    return 1;
  }
  mco.yamal = ytp_yamal_new(fd, &error);
  if (error) {
    lwsl_err("could not create yamal with error %s\n", fmc_error_msg(error));
    return 1;
  }
  auto *streams = ytp_streams_new(mco.yamal, &error);
  if (error) {
    lwsl_err("could not create stream with error %s\n", fmc_error_msg(error));
    return 1;
  }

  string_view vpeer(peer);
  string encoding = "Content-Type application/json\n"
                    "Content-Schema Coinbase";
  ostringstream ss;
  bool first = true;
  constexpr string_view prefix = "raw/coinbase/";
  for (auto &&sec : secs) {
    string chstr = string(prefix) + sec + "full";
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
    auto chview = string_view(channel, csz).substr(prefix.size());
    mco.streams.emplace(sec, stream);
    ss << (first ? "" : ",") << "\""<<sec << "\"";
    first = false;
  }
  std::string timestamp = std::to_string(fmc_cur_time_ns() / 1000000000);
  std::string what = timestamp + "GET" + "/users/self/verify";
  std::string signature = hmac_base64(mco.secret, what);
  mco.subscription = std::string(LWS_SEND_BUFFER_PRE_PADDING, '\0') +
    "{\"type\":\"subscribe\",\"product_ids\":["+ss.str()+"],\"channels\":[\"full\",\"heartbeat\"]," +
    "\"key\":\"" + mco.apikey + "\",\"signature\":\"" + signature + 
    "\",\"timestamp\":"+timestamp+",\"passphrase\":\"" + mco.passphrase + "\"}" +
    std::string(LWS_SEND_BUFFER_POST_PADDING, '\0');

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
    return 1;
  }

  /* schedule the first client connection attempt to happen immediately */
  lws_sul_schedule(context, 0, &mco.sul, connect_client, 1);

  for (int n = 0; n >= 0 && !interrupted;)
    n = lws_service(context, 0);

  lws_context_destroy(context);

  ytp_streams_del(streams, &error);
  ytp_yamal_del(mco.yamal, &error);

  lwsl_user("Completed\n");

  return 0;
}
