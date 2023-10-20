/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
 *****************************************************************************/

#include <ctype.h>
#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>

#include <functional>
#include <memory>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <fstream>

#include <cmp/cmp.h>
#include <fmc++/error.hpp>
#include <fmc++/logger.hpp>
#include <fmc++/mpl.hpp>
#include <fmc++/serialization.hpp>
#include <fmc++/strings.hpp>
#include <fmc++/time.hpp>
#include <fmc/cmdline.h>
#include <fmc/files.h>
#include <fmc/time.h>
#include <tuple>
#include <ytp/announcement.h>
#include <ytp/data.h>
#include <ytp/streams.h>
#include <ytp/yamal.h>
#include "kraken-parser.hpp"
#include "common.hpp"

using namespace std;
using namespace fmc;

struct binance_parse_ctx {
  string_view bidqt = "null"sv;
  string_view askqt = "null"sv;
  string_view bidpx = "null"sv;
  string_view askpx = "null"sv;
  string_view symbol;
  bool announced = false;
};

pair<string_view, parser_t> get_binance_channel_in(string_view sv,
                                                   fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  auto none = make_pair<string_view, parser_t>(string_view(), nullptr);
  RETURN_ERROR_UNLESS(pos != sv.npos, error, none,
                      "missing @ in the Binance stream name", sv);

  auto feedtype = sv.substr(pos + 1);
  auto outsv = sv.substr(0, pos);
  if (feedtype == "bookTicker") {
    // This section here is binance parsing code
    auto parse_binance_bookTicker =
        [ctx = binance_parse_ctx{}](string_view in, cmp_str_t *cmp, int64_t tm,
                                    uint64_t *last, bool skip,
                                    fmc_error_t **error) mutable {
          auto [val, rem] = simple_json_parse(in, "\"u\":");
          RETURN_ERROR_UNLESS(val.size(), error, false,
                              "could not parse message", in);
          auto [seqno, parsed] = fmc::from_string_view<uint64_t>(val);
          RETURN_ERROR_UNLESS(val.size() == parsed.size(), error, false,
                              "could not parse message", in);
          if (seqno <= *last)
            return false;
          *last = seqno;
          string_view bidqt;
          string_view askqt;
          string_view bidpx;
          string_view askpx;
          tie(bidpx, rem) = simple_json_parse(rem, "\"b\":\"", "\",");
          RETURN_ERROR_UNLESS(bidpx.size(), error, false,
                              "could not parse message", in);
          tie(bidqt, rem) = simple_json_parse(rem, "\"B\":\"", "\",");
          RETURN_ERROR_UNLESS(bidqt.size(), error, false,
                              "could not parse message", in);
          tie(askpx, rem) = simple_json_parse(rem, "\"a\":\"", "\",");
          RETURN_ERROR_UNLESS(askpx.size(), error, false,
                              "could not parse message", in);
          tie(askqt, rem) = simple_json_parse(rem, "\"A\":\"", "\"}");
          RETURN_ERROR_UNLESS(askqt.size(), error, false,
                              "could not parse message", in);

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
          bool announce = (!ctx.announced) & (bid_add | ask_add);
          ctx.announced |= announce;

          ctx.bidpx = bidpx;
          ctx.bidqt = bidqt;
          ctx.askpx = askpx;
          ctx.askqt = askqt;

          if (skip)
            return true;

          if (announce) {
            // ORE Book Control Message
            // [13, receive, vendor offset, vendor seqno, batch, imnt id,
            // uncross, command]
            cmp_ore_write(cmp, error,
                          (uint8_t)13,     // Message Type ID
                          (int64_t)tm,     // recv_time
                          (int64_t)0,      // vendor_offset
                          (uint64_t)0,     // vendor_seqno
                          (uint8_t)1,      // batch
                          (int32_t)chanid, // imnt id
                          (uint8_t)0,      // uncross
                          'C'              // command
            );
            if (*error)
              return false;
          }

          if (bid_mod) {
            // ORE Order Modify Message
            // [6, receive, vendor offset, vendor seqno, batch, imnt id, id, new
            // id, new price, new qty]
            cmp_ore_write(cmp, error,
                          (uint8_t)6,  // Message Type ID
                          (int64_t)tm, // recv_time
                          (int64_t)0,  // vendor_offset
                          (uint64_t)seqno,
                          (uint8_t)batch,  // batch (firts message)
                          (int32_t)chanid, // imnt_id
                          (int32_t)chanid, // order_id
                          (int32_t)chanid, // new_order_id
                          bidpx,           // price
                          bidqt,           // qty
                          (uint8_t) true   // is_bid
            );
          } else if (bid_add) {
            // ORE Order Add Message
            // [1, receive, vendor offset, vendor seqno, batch, imnt id, id,
            // price, qty, is bid]
            cmp_ore_write(cmp, error,
                          (uint8_t)1,  // Message Type ID
                          (int64_t)tm, // recv_time
                          (int64_t)0,  // vendor_offset
                          (uint64_t)seqno,
                          (uint8_t)batch,  // batch (firts message)
                          (int32_t)chanid, // imnt_id
                          (int32_t)chanid, // order_id
                          bidpx,           // price
                          bidqt,           // qty
                          true             // is_bid
            );
          } else if (bid_del) {
            // ORE Order Delete Message
            // [5, receive, vendor offset, vendor seqno, batch, imnt id, id]
            cmp_ore_write(cmp, error,
                          (uint8_t)5,  // Message Type ID
                          (int64_t)tm, // recv_time
                          (int64_t)0,  // vendor_offset
                          (uint64_t)seqno,
                          (uint8_t)batch,  // batch (firts message)
                          (int32_t)chanid, // imnt_id
                          (int32_t)chanid  // order_id
            );
          }
          if (*error)
            return false;

          if (ask_mod) {
            // ORE Order Modify Message
            // [6, receive, vendor offset, vendor seqno, batch, imnt id, id, new
            // id, new price, new qty]
            cmp_ore_write(cmp, error,
                          (uint8_t)6,  // Message Type ID
                          (int64_t)tm, // recv_time
                          (int64_t)0,  // vendor_offset
                          (uint64_t)seqno,
                          (uint8_t)0,            // batch (last batch message)
                          (int32_t)chanid,       // imnt_id
                          (int32_t)(chanid + 1), // order_id
                          (int32_t)(chanid + 1), // new_order_id
                          askpx,                 // price
                          askqt                  // qty
            );
          } else if (ask_add) {
            // ORE Order Add Message
            // [1, receive, vendor offset, vendor seqno, batch, imnt id, id,
            // price, qty, is bid]
            cmp_ore_write(cmp, error,
                          (uint8_t)1,  // Message Type ID
                          (int64_t)tm, // recv_time
                          (int64_t)0,  // vendor_offset
                          (uint64_t)seqno,
                          (uint8_t)0,            // batch (last batch message)
                          (int32_t)chanid,       // imnt_id
                          (int32_t)(chanid + 1), // order_id
                          askpx,                 // price
                          askqt,                 // qty
                          false                  // is_bid
            );
          } else if (ask_del) {
            // ORE Order Delete Message
            // [5, receive, vendor offset, vendor seqno, batch, imnt id, id]
            cmp_ore_write(cmp, error,
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
    return {outsv, parse_binance_bookTicker};
  } else if (feedtype == "trade") {
    auto parse_binance_trade = [](string_view in, cmp_str_t *cmp, int64_t tm,
                                  uint64_t *last, bool skip,
                                  fmc_error_t **error) {
      auto [val, rem] = simple_json_parse(in, "\"E\":");
      RETURN_ERROR_UNLESS(val.size(), error, false, "could not parse message",
                          in);
      auto [vend_ms, parsed] = fmc::from_string_view<int64_t>(val);
      RETURN_ERROR_UNLESS(val.size() == parsed.size(), error, false,
                          "could not parse message", in);

      tie(val, rem) = simple_json_parse(rem, "\"t\":");
      RETURN_ERROR_UNLESS(val.size(), error, false, "could not parse message",
                          in);
      auto [seqno, parsed2] = fmc::from_string_view<uint64_t>(val);
      RETURN_ERROR_UNLESS(val.size() == parsed2.size(), error, false,
                          "could not parse message", in);

      if (seqno <= *last)
        return false;
      *last = seqno;
      string_view trdpx;
      string_view trdqt;
      string_view isbid;
      tie(trdpx, rem) = simple_json_parse(rem, "\"p\":\"", "\",");
      RETURN_ERROR_UNLESS(trdpx.size(), error, false, "could not parse message",
                          in);
      tie(trdqt, rem) = simple_json_parse(rem, "\"q\":\"", "\",");
      RETURN_ERROR_UNLESS(trdqt.size(), error, false, "could not parse message",
                          in);

      tie(isbid, rem) = simple_json_parse(rem, "\"m\":");
      RETURN_ERROR_UNLESS(isbid.size(), error, false, "could not parse message",
                          in);

      // ORE Off Book Trade Message
      // [11, receive, vendor offset, vendor seqno, batch, imnt id, trade
      // price, qty, decorator]
      cmp_ore_write(cmp, error,
                    (uint8_t)11,                         // Message Type ID
                    (int64_t)tm,                         // receive
                    (int64_t)(tm - vend_ms * 1000000LL), // vendor offset in ns
                    (uint64_t)seqno,                     // vendor seqno
                    (uint8_t)0,                          // batch
                    (uint64_t)chanid,                    // imnt_id
                    trdpx,                               // trade price
                    trdqt,                               // qty
                    string_view(isbid == "true" ? "b" : "a"));

      return *error == nullptr;
    };
    return {outsv, parse_binance_trade};
  }
  RETURN_ERROR(error, none, "unknown Binance stream type", feedtype);
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
  using channels_in_t = unordered_map<string_view, unique_ptr<stream_in_t>>;
  using streams_in_t = unordered_map<ytp_mmnode_offs, stream_in_t *>;
  // This map contains a context factory for each supported feed
  unordered_map<string, resolver_t> resolvers = {
      {"binance", get_binance_channel_in},
      {"kraken", get_kraken_channel_in}};
  // Hash map to keep track of outgoing streams
  streams_out_t s_out;
  channels_in_t ch_in;
  streams_in_t s_in;
  string_view prefix_out = "ore/";
  string_view prefix_in = "raw/";
  string_view encoding = "Content-Type application/msgpack\n"
                         "Content-Schema ore1.1.3";
  const char *peer = nullptr;
  const char *mappings_file = nullptr;
  struct string_hash
  {
      using hash_type = hash<string_view>;
      using is_transparent = void;
  
      size_t operator()(const char* str) const        { return hash_type{}(str); }
      size_t operator()(string_view str) const   { return hash_type{}(str); }
      size_t operator()(string const& str) const { return hash_type{}(str); }
  };
  unordered_map<string, string, string_hash, equal_to<>> mappings;
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
  if (streams)
    ytp_streams_del(streams, &error);
  if (ytp_in)
    ytp_yamal_del(ytp_in, &error);
  if (ytp_out)
    ytp_yamal_del(ytp_out, &error);
  if (fd_in != -1)
    fmc_fclose(fd_in, &error);
  if (fd_out != -1)
    fmc_fclose(fd_out, &error);
}

void runner_t::init(fmc_error_t **error) {
  fd_in = fmc_fopen(ytp_file_in, fmc_fmode::READ, error);
  RETURN_ON_ERROR(error, , "could not open input yamal file", ytp_file_in);
  fd_out = fmc_fopen(ytp_file_out, fmc_fmode::READWRITE, error);
  RETURN_ON_ERROR(error, , "could not open output yamal file", ytp_file_out);
  ytp_in = ytp_yamal_new(fd_in, error);
  RETURN_ON_ERROR(error, , "could not create input yamal");
  ytp_out = ytp_yamal_new(fd_out, error);
  RETURN_ON_ERROR(error, , "could not create output yamal");
  streams = ytp_streams_new(ytp_out, error);
  RETURN_ON_ERROR(error, , "could not create stream");
  if (mappings_file) {
    ifstream mppings{mappings_file};
    if (!mppings) {
      RETURN_ON_ERROR(error, , "failed to open mappings file %s", mappings_file);
    }
    vector<string> secs{istream_iterator<string>(mppings),
                        istream_iterator<string>()};
    for (auto &sec :secs) {
        auto [mkt, sep, tickers] = split(sec, ",");
        auto [mkt_ticker, sep2, norm_ticker] = split(tickers, ",");
        mappings.emplace(string(mkt) + "/" + string(mkt_ticker), string(mkt) + "/" + string(norm_ticker));
    }
  }
}

void runner_t::recover(fmc_error_t **error) {
  // This is where we do recovery. We count the number of messages we written
  // for each channel. Then we skip the correct number of messages for each
  // channel from the input to recover
  uint64_t msg_count = 0ULL;
  uint64_t chn_count = 0ULL;
  constexpr auto msg_batch = 1000000ULL;
  constexpr auto chn_batch = 1000ULL;
  auto it_out = ytp_data_begin(ytp_out, error);
  RETURN_ON_ERROR(error, , "could not obtain iterator");
  for (; !ytp_yamal_term(it_out) && !interrupted;
       it_out = ytp_yamal_next(ytp_out, it_out, error)) {
    RETURN_ON_ERROR(error, , "could not obtain iterator");
    uint64_t seqno;
    int64_t ts;
    ytp_mmnode_offs stream;
    size_t sz;
    const char *data;
    ytp_data_read(ytp_out, it_out, &seqno, &ts, &stream, &sz, &data, error);
    RETURN_ON_ERROR(error, , "could not read data");
    auto *chan = get_stream_out(stream, error);
    RETURN_ON_ERROR(error, , "could not create output stream");
    if (!chan)
      continue;
    chn_count += chan->count == 0ULL;
    ++chan->count;
    if (++msg_count % msg_batch == 0 || chn_count % chn_batch == 0) {
      notice("so far recovered", msg_count, "messages on", chn_count,
             "channels...");
    }
  }
  notice("recovered", msg_count, "messages on", chn_count, "channels");
}

void runner_t::run(fmc_error_t **error) {
  cmp_str_t cmp;
  cmp_str_init(&cmp);
  auto it_in = ytp_data_begin(ytp_in, error);
  RETURN_ON_ERROR(error, , "could not obtain iterator");
  int64_t last = fmc_cur_time_ns();
  constexpr auto delay = 1000000000LL;
  uint64_t read_count = 0ULL;
  uint64_t msg_count = 0ULL;
  uint64_t dup_count = 0ULL;
  while (!interrupted) {
    for (; !ytp_yamal_term(it_in);
         it_in = ytp_yamal_next(ytp_in, it_in, error)) {
      RETURN_ON_ERROR(error, , "could not obtain iterator");
      uint64_t seqno;
      int64_t ts;
      ytp_mmnode_offs stream;
      size_t sz;
      const char *data;
      ytp_data_read(ytp_in, it_in, &seqno, &ts, &stream, &sz, &data, error);
      RETURN_ON_ERROR(error, , "could not obtain iterator");
      auto *info = get_stream_in(stream, error);
      if (*error)
        return;
      // if this channel not interesting, skip it
      if (!info)
        continue;
      ++read_count;
      seqno = info->seqno;
      cmp_str_reset(&cmp);
      bool skip = info->outinfo->count > 0;
      bool nodup =
          info->parser(string_view(data, sz), &cmp, ts, &seqno, skip, error);
      if (*error)
        return;
      // duplicate
      if (!nodup) {
        ++dup_count;
        continue;
      }
      info->seqno = seqno;
      // otherwise check if we still recovering
      if (skip) {
        --info->outinfo->count;
        continue;
      }
      size_t bufsz = cmp_str_size(&cmp);
      auto dst = ytp_data_reserve(ytp_out, bufsz, error);
      RETURN_ON_ERROR(error, , "could not reserve message");
      memcpy(dst, cmp_str_data(&cmp), bufsz);
      ytp_data_commit(ytp_out, fmc_cur_time_ns(), info->outinfo->stream, dst,
                      error);
      RETURN_ON_ERROR(error, , "could not commit message");
      ++msg_count;
    }
    if (auto now = fmc_cur_time_ns(); last + delay < now) {
      last = now;
      notice("read:", read_count, "written:", msg_count,
             "duplicates:", dup_count);
      read_count = 0ULL;
      msg_count = 0ULL;
      dup_count = 0ULL;
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
  RETURN_ON_ERROR(error, nullptr, "could not look up stream");
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
  if (auto it = mappings.find(sv);it != mappings.end()) {
    chstr.append(it->second);
  } else {
    chstr.append(sv);
  }
  auto stream = ytp_streams_announce(streams, vpeer.size(), vpeer.data(),
                                     chstr.size(), chstr.data(),
                                     encoding.size(), encoding.data(), error);
  RETURN_ON_ERROR(error, nullptr, "could not announce stream");
  return emplace_stream_out(stream);
}

runner_t::stream_in_t *runner_t::get_stream_in(ytp_mmnode_offs stream,
                                               fmc_error_t **error) {
  fmc_error_clear(error);

  // Look up the stream in the input stream map
  auto where = s_in.find(stream);
  if (where != s_in.end())
    return where->second;

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
  RETURN_ON_ERROR(error, nullptr, "could not look up stream announcement");
  string_view sv{channel, csz};
  // if this stream is one of ours or wrong format, skip
  if (string_view(origpeer, psz) == peer || !starts_with(sv, prefix_in)) {
    return s_in.emplace(stream, nullptr).first->second;
  }

  sv = sv.substr(prefix_in.size());
  auto chan_it = ch_in.find(sv);
  if (chan_it == ch_in.end()) {
    // we remove the prefix from the input channel name
    auto [feedsv, sep, rem] = split(sv, "/");
    auto feed = string(feedsv);
    auto resolver = resolvers.find(feed);
    RETURN_ERROR_UNLESS(resolver != resolvers.end(), error, nullptr,
                        "unknown feed", feed);
    auto [outsv, parser] = resolver->second(sv, error);
    RETURN_ON_ERROR(error, nullptr, "could not find a parser");
    auto *outinfo = get_stream_out(outsv, error);
    RETURN_ON_ERROR(error, nullptr, "could not get out stream");
    chan_it = ch_in
                  .emplace(sv, make_unique<stream_in_t>(stream_in_t{
                                   .parser = parser, .outinfo = outinfo}))
                  .first;
  }
  return s_in.emplace(stream, chan_it->second.get()).first->second;
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
      /* 2 */ {"--mappings", false, &runner.mappings_file},
      /* 3 */ {"--ytp-input", true, &runner.ytp_file_in},
      /* 4 */ {"--ytp-output", true, &runner.ytp_file_out},
      {NULL}};
  fmc_cmdline_opt_proc(argc, argv, options, &error);
  if (options[0].set) {
    printf("feed-parse --peer PEER --ytp-input FILE --ytp-output FILE\n\n"
           "Feed Parser.\n\n"
           "Application parses data produced by the feed handler.\n");
    return 0;
  }
  EXIT_ON_ERROR(&error);

  runner.init(&error);
  EXIT_ON_ERROR(&error);

  runner.recover(&error);
  EXIT_ON_ERROR(&error);

  runner.run(&error);
  EXIT_ON_ERROR(&error);

  return 0;
}
