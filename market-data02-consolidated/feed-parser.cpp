/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.

 *****************************************************************************/

#include <ctype.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>

#include <functional>
#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>

#include <cmp/cmp.h>
#include <fmc++/serialization.hpp>
#include <fmc++/strings.hpp>
#include <fmc/cmdline.h>
#include <fmc/files.h>
#include <fmc/time.h>
#include <tuple>
#include <ytp/announcement.h>
#include <ytp/data.h>
#include <ytp/streams.h>
#include <ytp/yamal.h>

using namespace std;

#define RETURN_ERROR_UNLESS(COND, ERR, RET, ...)                               \
  if (__builtin_expect(!(COND), 0)) {                                          \
    fmc_error_set(ERR, __VA_ARGS__);                                           \
    return RET;                                                                \
  }

// If you compiling with C++20 you don't need this
inline bool starts_with(string_view a, string_view b) {
  return a.substr(0, b.size()) == b;
}

inline tuple<string_view, string_view, string_view> split(string_view a,
                                                          string_view sep) {
  auto pos = a.find_first_of(sep);
  return {a.substr(0, pos), a.substr(pos, sep.size()),
          a.substr(pos + sep.size())};
}

// passing json string and json key
// return parsed value and remainder after value
inline pair<string_view, string_view>
simple_json_parse(string_view a, string_view key, string_view sep = ","sv) {
  auto pos = a.find(key);
  if (pos == string_view::npos)
    return {string_view(), string_view()};
  a = a.substr(pos + a.size());
  pos = a.find_first_of(sep);
  if (pos == string_view::npos)
    return {string_view(), string_view()};
  return { a.substr(p, pos), a.substr(pos + sep.size()) }
}

template <class... Args>
static void cmp_ore_write(cmp_str_t *cmp, fmc_error_t **error, Args &&...args) {
  uint32_t left = sizeof...(Args);
  cmp_ctx_t *ctx = &(cmp->ctx);
  fmc_error_clear(error);

  // Encode to cmp
  bool ret = cmp_write_array(ctx, left);
  if (!ret) {
    FMC_ERROR_REPORT(error, cmp_strerror(ctx));
    return;
  }
  ret = cmp_write_many(ctx, &left, args...);
  if (!ret) {
    FMC_ERROR_REPORT(error, cmp_strerror(ctx));
    return;
  }
}

// Parser gets the original data, string to write data to
// sequence number processed and error.
// Sets error if could not parse.
// Returns true is processed, false if duplicated.
using parser_t =
    function<bool(string_view, cmp_str_t *, uint64_t *, fmc_error_t **)>;
typedef pair<string_view, parser_t> (*resolver_t)(string_view, fmc_error_t **);

struct binance_parse_ctx {
  string_view bidqt = "null"sv;
  string_view askqt = "null"sv;
  string_view bidpx = "null"sv;
  string_view askpx = "null"sv;
  string_view symbol bool first = true;
};

constexpr int32_t chanid = 100;

// This section here is binance parsing code
auto parse_binance_bookTicker =
    [ctx = binance_parse_ctx{}](string_view in, cmp_str_t *cmp, int64_t tm,
                                uint64_t *last, bool skip,
                                fmc_error_t **error) mutable {
      auto [val, rem] = simple_json_parse(in, "\"u\":");
      RETURN_ERROR_UNLESS(val.size(), error, false,
                          "could not parse message %s", string(in));
      auto [seqno, parsed] = from_string_view(val);
      RETURN_ERROR_UNLESS(val.size() == parsed.size(), error, false,
                          "could not parse message %s", string(in));
      if (seqno <= last)
        return false;
      *last = seqno;
      string_view bidqt;
      string_view askqt;
      string_view bidpx;
      string_view askpx;
      tie(bidpx, rem) = simple_json_parse(rem, "\"b\":\"", "\",");
      RETURN_ERROR_UNLESS(bidpx.size(), error, false,
                          "could not parse message %s", string(in));
      tie(bidqt, rem) = simple_json_parse(rem, "\"B\":\"", "\",");
      RETURN_ERROR_UNLESS(bidqt.size(), error, false,
                          "could not parse message %s", string(in));
      tie(askpx, rem) = simple_json_parse(rem, "\"a\":\"", "\",");
      RETURN_ERROR_UNLESS(askpx.size(), error, false,
                          "could not parse message %s", string(in));
      tie(askqt, rem) = simple_json_parse(rem, "\"A\":\"", "\"}");
      RETURN_ERROR_UNLESS(askqt.size(), error, false,
                          "could not parse message %s", string(in));

      // TODO: need to fix this
      bool has_bid = bidpx != "null";
      bool has_ask = askpx != "null";
      bool had_bid = ctx.bidpx != "null";
      bool had_ask = ctx.askpx != "null";
      bool bid_mod = had_bid & has_bid & (bidpx == ctx.bidpx);
      bool ask_mod = had_ask & has_ask & (askpx == ctx.askpx);
      bool bid_add = !had_bid & has_bid;
      bool ask_add = !had_ask & has_ask;
      bool bid_del = had_bid & !has_bid;
      bool ask_del = had_ask & !has_ask;

      bool batch = ask_mod | ask_add | ask_del;

      ctx.bidpx = bidpx;
      ctx.bidqt = bidqt;
      ctx.askpx = askpx;
      crx.askqt = askqt;

      if (skip)
        return;

  if (ask_mod) {
    // ORE Order Modify Message
    // [6, receive, vendor offset, vendor seqno, batch, imnt id, id, new
    // id, new price, new qty]
    cmp_ore_write(
        cmp, &error,
        (uint8_t)6,                // Message Type ID
        (int64_t)tm,      // recv_time
        (int64_t)0, // vendor_offset
        (uint64_t)seqno,
        (uint8_t)0,           // batch (last batch message)
        (int32_t)chanid, // imnt_id
        (int32_t)(chanid + 1), // order_id
        (int32_t)(chanid + 1), // new_order_id
        askpx,                   // price
        askqt         // qty
    );
  } else if (ask_add) {
    // ORE Order Add Message
    // [1, receive, vendor offset, vendor seqno, batch, imnt id, id,
    // price, qty, is bid]
    cmp_ore_write(
        cmp, &error,
        (uint8_t)1,                // Message Type ID
        (int64_t)tm,      // recv_time
        (int64_t)0, // vendor_offset
        (uint64_t)seqno,
        (uint8_t)0,           // batch (last batch message)
        (int32_t)chanid, // imnt_id
        (int32_t)(chanid + 1), // order_id
        askpx,                   // price
        askqt,        // qty
        false                                     // is_bid
    );
  } else if (ask_del) {
    // ORE Order Delete Message
    // [5, receive, vendor offset, vendor seqno, batch, imnt id, id]
    cmp_ore_write(
        cmp, &error,
        (uint8_t)5,                // Message Type ID
        (int64_t)tm,      // recv_time
        (int64_t)0, // vendor_offset
        (uint64_t)seqno,
        (uint8_t)0,                              // batch (last batch message)
        (int32_t)chanid,                    // imnt_id
        (int32_t)(chanid + 1) // order_id
    );
  }
      
  if (ask_mod) {
    // ORE Order Modify Message
    // [6, receive, vendor offset, vendor seqno, batch, imnt id, id, new
    // id, new price, new qty]
    cmp_ore_write(cmp, &error,
                  (uint8_t)6,  // Message Type ID
                  (int64_t)tm, // recv_time
                  (int64_t)0,  // vendor_offset
                  (uint64_t)seqno,
                  (uint8_t)0,            // batch (last batch message)
                  (int32_t)chanid,       // imnt_id
                  (int32_t)(chanid + 1), // order_id
                  (int32_t)(chanid + 1), // new_order_id
                  (int64_t)askpx,        // price
                  (int32_t)askqt         // qty
    );
  } else if (ask_add) {
    // ORE Order Add Message
    // [1, receive, vendor offset, vendor seqno, batch, imnt id, id,
    // price, qty, is bid]
    cmp_ore_write(cmp, &error,
                  (uint8_t)1,  // Message Type ID
                  (int64_t)tm, // recv_time
                  (int64_t)0,  // vendor_offset
                  (uint64_t)seqno,
                  (uint8_t)0,            // batch (last batch message)
                  (int32_t)chanid,       // imnt_id
                  (int32_t)(chanid + 1), // order_id
                  (int64_t)askpx,        // price
                  (int32_t)askqt,        // qty
                  false                  // is_bid
    );
  } else if (ask_del) {
    // ORE Order Delete Message
    // [5, receive, vendor offset, vendor seqno, batch, imnt id, id]
    cmp_ore_write(cmp, &error,
                  (uint8_t)5,  // Message Type ID
                  (int64_t)tm, // recv_time
                  (int64_t)0,  // vendor_offset
                  (uint64_t)seqno,
                  (uint8_t)0,           // batch (last batch message)
                  (int32_t)chanid,      // imnt_id
                  (int32_t)(chanid + 1) // order_id
    );
  }

  return *error == nullptr;
};

bool parse_binance_trade(string_view in, cmp_str_t *cmp, int64_t tm,
                         uint64_t *last, bool skip, fmc_error_t **error) {
  auto [val, rem] = simple_json_parse(in, "\"E\":");
  RETURN_ERROR_UNLESS(val.size(), error, false, "could not parse message %s",
                      string(in));
  auto [etime_ms, parsed] = from_string_view(val);
  RETURN_ERROR_UNLESS(val.size() == parsed.size(), error, false,
                      "could not parse message %s", string(in));

  tie(val, rem) = simple_json_parse(rem, "\"E\":");
  RETURN_ERROR_UNLESS(val.size(), error, false, "could not parse message %s",
                      string(in));
  auto [seqno, parsed2] = from_string_view(val);
  RETURN_ERROR_UNLESS(val.size() == parsed2.size(), error, false,
                      "could not parse message %s", string(in));

  if (seqno <= last)
    return false;
  *last = seqno;
  string_view trdpx;
  string_view trdqt;
  string_view isbid;
  tie(trdpx, rem) = simple_json_parse(rem, "\"p\":\"", "\",");
  RETURN_ERROR_UNLESS(bidpx.size(), error, false, "could not parse message %s",
                      string(in));
  tie(trdqt, rem) = simple_json_parse(rem, "\"q\":\"", "\",");
  RETURN_ERROR_UNLESS(bidqt.size(), error, false, "could not parse message %s",
                      string(in));

  tie(isbid, rem) = simple_json_parse(rem, "\"m\":");
  RETURN_ERROR_UNLESS(bidqt.size(), error, false, "could not parse message %s",
                      string(in));

  // ORE Off Book Trade Message
  // [11, receive, vendor offset, vendor seqno, batch, imnt id, trade
  // price, qty, decorator]
  cmp_ore_write(cmp, error,
                (uint8_t)11,        // Message Type ID
                (int64_t)tm,        // receive
                (int64_t)vendoroff, // vendor offset
                (uint64_t)seqno,    // vendor seqno
                (uint8_t)0,         // batch
                (uint64_t)chanid,   // imnt_id
                trdpx,              // trade price
                trdqt,              // qty
                (uint8_t)(isbid == 'true' ? 'b' : 'a'));

  return *error == nullptr;
}

pair<string_view, parser_t> get_binance_channel_in(string_view sv,
                                                   fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  if (pos == sv.npos) {
    fmc_error_set(error, "missing @ in the Binance stream name %s",
                  string(sv).c_str());
    return {string_view(), nullptr};
  }
  auto feedtype = sv.substr(pos + 1);
  auto outsv = sv.substr(0, pos);
  if (feedtype == "bookTicker") {
    return {outsv, parse_binance_bookTicker};
  } else if (feedtype == "trade") {
    return {outsv, parse_binance_trade};
  }
  fmc_error_set(error, "unknown Binance stream type %s",
                string(feedtype).c_str());
  return {string_view(), nullptr};
}

static int interrupted = 0;
static void sigint_handler(int sig) { interrupted = 1; }

struct runner_t {
  // This is where we store information about channel processed
  struct stream_out_t {
    ytp_mmnode_offs stream = 0ULL;
    uint64_t count = 0;
  };

  struct stream_in_t {
    parser_t parser;
    struct stream_out_t *outinfo = nullptr;
    uint64_t seqno = 0ULL;
  };

  ~runner_t();
  void init(fmc_error_t **error);
  void recover(fmc_error_t **error);
  void run(fmc_error_t **error);

  stream_out_t *get_stream_out(ytp_mmnode_offs stream, fmc_error_t **error);
  stream_out_t *get_stream_out(string_view sv, fmc_error_t **error);
  stream_in_t *get_stream_in(ytp_mmnode_offs stream, fmc_error_t **error);
  stream_out_t *emplace_stream_out(ytp_mmnode_offs stream);

  // We use a hash map to store stream info
  using streams_out_t =
      unordered_map<ytp_mmnode_offs, unique_ptr<stream_out_t>>;
  using streams_in_t = unordered_map<ytp_mmnode_offs, stream_in_t>;
  // This map contains a context factory for each supported feed
  unordered_map<string, resolver_t> resolvers = {
      {"binance", get_binance_channel_in}};
  // Hash map to keep track of outgoing streams
  streams_out_t s_out;
  streams_in_t s_in;
  string_view prefix_out = "ore/";
  string_view prefix_in = "raw/";
  string_view encoding = "";
  const char *peer = nullptr;
  const char *ytp_file_in = nullptr;
  const char *ytp_file_out = nullptr;
  fmc_fd fd_in = -1;
  fmc_fd fd_out = -1;
  ytp_yamal_t *ytp_in = nullptr;
  ytp_yamal_t *ytp_out = nullptr;
  ytp_streams_t *streams = nullptr;
};

runner_t::~runner_t() {
  fmc_error_t *error = nullptr;
  ytp_streams_del(streams, &error);
  ytp_yamal_del(ytp_in, &error);
  ytp_yamal_del(ytp_out, &error);
  fmc_fclose(fd_in, &error);
  fmc_fclose(fd_out, &error);
}

void runner_t::init(fmc_error_t **error) {
  fd_in = fmc_fopen(ytp_file_in, fmc_fmode::READ, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not open input yamal file %s",
                  ytp_file_in);
    return;
  }

  fd_out = fmc_fopen(ytp_file_out, fmc_fmode::READWRITE, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not open output yamal file %s",
                  ytp_file_out);
    return;
  }

  ytp_in = ytp_yamal_new(fd_in, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not create input yamal");
    return;
  }

  ytp_out = ytp_yamal_new(fd_out, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not create output yamal");
    return;
  }

  streams = ytp_streams_new(ytp_out, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not create stream");
    return;
  }
}

void runner_t::recover(fmc_error_t **error) {
  // This is where we do recovery. We count the number of messages we written
  // for each channel. Then we skip the correct number of messages for each
  // channel from the input to recover
  auto it_out = ytp_data_begin(ytp_out, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not obtain iterator");
    return;
  }
  for (; !ytp_yamal_term(it_out) && !interrupted;
       it_out = ytp_yamal_next(ytp_in, it_out, error)) {
    if (*error) {
      fmc_error_add(error, "; ", "could not obtain iterator");
      return;
    }
    uint64_t seqno;
    int64_t ts;
    ytp_mmnode_offs stream;
    size_t sz;
    const char *data;
    ytp_data_read(ytp_in, it_out, &seqno, &ts, &stream, &sz, &data, error);
    if (error) {
      fmc_error_add(error, "; ", "could not read data");
      return;
    }
    auto *chan = get_stream_out(stream, error);
    if (error) {
      fmc_error_add(error, "; ", "could not create output stream");
      return;
    }
    if (!chan)
      continue;
    ++chan->count;
  }
}

void runner_t::run(fmc_error_t **error) {
  cmp_str_t cmp;
  cmp_str_init(&cmp);
  auto it_in = ytp_data_begin(ytp_in, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not obtain iterator");
    return;
  }
  while (!interrupted) {
    for (; !ytp_yamal_term(it_in);
         it_in = ytp_yamal_next(ytp_in, it_in, error)) {
      if (*error) {
        fmc_error_add(error, "; ", "could not obtain iterator");
        return;
      }
      uint64_t seqno;
      int64_t ts;
      ytp_mmnode_offs stream;
      size_t sz;
      const char *data;
      ytp_data_read(ytp_in, it_in, &seqno, &ts, &stream, &sz, &data, error);
      if (*error) {
        fmc_error_add(error, "; ", "could not obtain iterator");
        return;
      }
      auto *info = get_stream_in(stream, error);
      if (*error)
        return;
      // if this channel not interesting, skip it
      if (!info->parser)
        continue;
      seqno = info->seqno;
      cmp_str_reset(&cmp);
      bool res = info->parser(string_view(data, sz), &cmp, &seqno, error);
      if (*error)
        return;
      // duplicate
      if (!res)
        continue;
      info->seqno = seqno;
      // otherwise check if we still recovering
      if (info->outinfo->count) {
        --info->outinfo->count;
        continue;
      }
      size_t bufsz = cmp_str_size(&cmp);
      auto dst = ytp_data_reserve(ytp_out, bufsz, error);
      if (*error) {
        fmc_error_add(error, "; ", "could not reserve message");
        return;
      }
      memcpy(dst, cmp_str_data(&cmp), bufsz);
      ytp_data_commit(ytp_out, fmc_cur_time_ns(), info->outinfo->stream, dst,
                      error);
      if (*error) {
        fmc_error_add(error, "; ", "could not commit message");
        return;
      }
    }
  }
}

runner_t::stream_out_t *runner_t::emplace_stream_out(ytp_mmnode_offs stream) {
  return s_out
      .emplace(stream, make_unique<stream_out_t>(stream_out_t{stream, 0ULL}))
      .first->second.get();
}

runner_t::stream_out_t *runner_t::get_stream_out(ytp_mmnode_offs stream,
                                                 fmc_error_t **error) {
  auto where = s_out.find(stream);
  // If we never seen this stream, we need to add it to the map of out streams
  // and if we care about this particular channel create info for this channel.
  if (where != s_out.end())
    return where->second.get();

  uint64_t seqno;
  size_t psz, csz, esz;
  const char *origpeer, *channel, *encoding;
  ytp_mmnode_offs *original, *subscribed;
  // This functions looks up stream announcement details
  ytp_announcement_lookup(ytp_out, stream, &seqno, &psz, &origpeer, &csz,
                          &channel, &esz, &encoding, &original, &subscribed,
                          error);
  if (*error) {
    fmc_error_add(error, "; ", "could not look up stream");
    return nullptr;
  }
  // if this stream is not one of ours or wrong format, skip
  if (string_view(origpeer, psz) != peer ||
      !starts_with(string_view{channel, csz}, prefix_out)) {
    return s_out.emplace(stream, nullptr).first->second.get();
  }
  return emplace_stream_out(stream);
}

runner_t::stream_out_t *runner_t::get_stream_out(string_view sv,
                                                 fmc_error_t **error) {
  auto vpeer = string_view(peer);
  string chstr;
  chstr.append(prefix_out);
  chstr.append(sv);
  auto stream = ytp_streams_announce(streams, vpeer.size(), vpeer.data(),
                                     chstr.size(), chstr.data(),
                                     encoding.size(), encoding.data(), error);
  if (*error) {
    fmc_error_add(error, "; ", "could not announce stream");
    return nullptr;
  }
  return emplace_stream_out(stream);
}

runner_t::stream_in_t *runner_t::get_stream_in(ytp_mmnode_offs stream,
                                               fmc_error_t **error) {
  fmc_error_clear(error);

  // Look up the stream in the input stream map
  auto where = s_in.find(stream);
  if (where != s_in.end())
    return &where->second;

  // if we don't know this input stream, look up stream info,
  // check if it is one of ours, if not check it starts with
  // correct prefix. If so, add this to the channel map
  uint64_t seqno;
  size_t psz, csz, esz;
  const char *origpeer, *channel, *encoding;
  ytp_mmnode_offs *original, *subscribed;
  // This functions looks up stream announcement details
  ytp_announcement_lookup(ytp_in, stream, &seqno, &psz, &origpeer, &csz,
                          &channel, &esz, &encoding, &original, &subscribed,
                          error);
  if (*error) {
    fmc_error_add(error, "; ", "could not look up stream announcement");
    return nullptr;
  }

  string_view sv{channel, csz};
  // if this stream is one of ours or wrong format, skip
  if (string_view(origpeer, psz) == peer || !starts_with(sv, prefix_in)) {
    return &s_in.emplace(stream, stream_in_t{}).first->second;
  }

  // we remove the prefix from the input channel name
  sv = sv.substr(prefix_in.size());
  auto feed = string(sv.substr(0, sv.find_first_of('/')));
  auto resolver = resolvers.find(feed);
  if (resolver == resolvers.end()) {
    fmc_error_set(error, "unknown feed %s", feed.c_str());
    return nullptr;
  }
  auto [outsv, parser] = resolver->second(sv, error);
  if (*error)
    return nullptr;
  auto *outinfo = get_stream_out(outsv, error);
  if (*error)
    return nullptr;
  return &s_in.emplace(stream,
                       stream_in_t{.parser = parser, .outinfo = outinfo})
              .first->second;
}

int main(int argc, const char **argv) {
  using namespace std;

  fmc_error_t *error = nullptr;

  // set up signal handler
  signal(SIGINT, sigint_handler);

  runner_t runner;

  // command line option processing
  fmc_cmdline_opt_t options[] = {
      /* 0 */ {"--help", false, NULL},
      /* 1 */ {"--peer", true, &runner.peer},
      /* 1 */ {"--ytp-input", true, &runner.ytp_file_in},
      /* 2 */ {"--ytp-output", true, &runner.ytp_file_out},
      {NULL}};
  fmc_cmdline_opt_proc(argc, argv, options, &error);
  if (options[0].set) {
    printf("feed-parse --peer PEER --ytp-input FILE --ytp-output FILE\n\n"
           "Feed Parser.\n\n"
           "Application parses data produced by the feed handler.\n");
    return 0;
  }
  if (error) {
    fprintf(stderr, "could not process args: %s\n", fmc_error_msg(error));
    return 1;
  }

  runner.init(&error);
  if (error) {
    fprintf(stderr, "could not initialize with error: %s\n",
            fmc_error_msg(error));
    return 1;
  }

  runner.recover(&error);
  if (error) {
    fprintf(stderr, "could not recover with error: %s\n", fmc_error_msg(error));
    return 1;
  }

  runner.run(&error);
  if (error) {
    fprintf(stderr, "run-time error: %s\n", fmc_error_msg(error));
    return 1;
  }

  return 0;
}
