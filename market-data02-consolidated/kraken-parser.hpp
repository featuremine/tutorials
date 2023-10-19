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

using namespace std;
using namespace fmc;

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
  a = a.substr(pos + key.size());
  pos = a.find_first_of(sep);
  if (pos == string_view::npos)
    return {string_view(), string_view()};
  return {a.substr(0, pos), a.substr(pos + sep.size())};
}

template <class... Args>
static void cmp_ore_write(cmp_str_t *cmp, fmc_error_t **error, Args &&...args) {
  uint32_t left = sizeof...(Args);
  cmp_ctx_t *ctx = &(cmp->ctx);
  fmc_error_clear(error);

  // Encode to cmp
  bool ret = cmp_write_array(ctx, left);
  RETURN_ERROR_UNLESS(ret, error, , "could not parse:", cmp_strerror(ctx));
  ret = cmp_write_many(ctx, &left, args...);
  RETURN_ERROR_UNLESS(ret, error, , "could not parse:", cmp_strerror(ctx));
}

// Parser gets the original data, string to write data to
// sequence number processed and error.
// Sets error if could not parse.
// Returns true is processed, false if duplicated.
using parser_t = function<bool(
    (string_view, cmp_str_t *, int64_t, uint64_t *, bool, fmc_error_t **))>;
typedef pair<string_view, parser_t> (*resolver_t)(string_view, fmc_error_t **);

constexpr int32_t chanid = 100;
struct kraken_parse_ctx {
  string_view bidqt = "null"sv;
  string_view askqt = "null"sv;
  string_view bidpx = "null"sv;
  string_view askpx = "null"sv;
  string_view symbol;
  bool announced = false;
};

pair<string_view, parser_t> get_kraken_channel_in(string_view sv,
                                                   fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  auto none = make_pair<string_view, parser_t>(string_view(), nullptr);
  RETURN_ERROR_UNLESS(pos != sv.npos, error, none,
                      "missing @ in the Kraken stream name", sv);

  auto feedtype = sv.substr(pos + 1);
  auto outsv = sv.substr(0, pos);
  if (feedtype == "spread") {
    /*
    [
      0, Channel ID of subscription - deprecated
      [
        "5698.40000", bid price
        "5700.00000", ask price
        "1542057299.545897", seconds since epoch
        "1.01234567", bid volume
        "0.98765432" ask volume
      ],
      "spread", message type
      "XBT/USD" ticker
    ]
    */
    // This section here is kraken parsing code
    auto parse_kraken_spread =
        [ctx = kraken_parse_ctx{}](string_view in, cmp_str_t *cmp, int64_t tm,
                                    uint64_t *last, bool skip,
                                    fmc_error_t **error) mutable {
          auto seqno = tm;
          auto [bidpx, rem] = simple_json_parse(in, "\"", "\"");
          RETURN_ERROR_UNLESS(bidpx.size(), error, false,
                              "could not parse message", in);
          auto [askpx, rem] = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(askpx.size(), error, false,
                              "could not parse message", in);
          auto [ts, rem] = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(ts.size(), error, false,
                              "could not parse message", in);
          auto [bidqt, rem] = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(bidqt.size(), error, false,
                              "could not parse message", in);
          auto [askqt, rem] = simple_json_parse(rem, "\"", "\"");
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
    return {outsv, parse_kraken_spread};
  } else if (feedtype == "trade") {
    /*
    [
      0,
      [
        [
          "5541.20000",
          "0.15850568",
          "1534614057.321597",
          "s",
          "l",
          ""
        ],
        [
          "6060.00000",
          "0.02455000",
          "1534614057.324998",
          "b",
          "l",
          ""
        ]
      ],
      "trade",
      "XBT/USD"
    ]
    */
    auto parse_kraken_trade = [](string_view in, cmp_str_t *cmp, int64_t tm,
                                  uint64_t *last, bool skip,
                                  fmc_error_t **error) {
      auto trades_pos = in.find("[", 1);
      //TODO: Handle error
      auto first_trade_pos = in.find("[", trades_pos);
      //TODO: Handle error
      auto rem = in.substr(first_trade_pos);
      std::string_view trademsg;
      while (true)
      {
        tie(trademsg, rem) = simple_json_parse(rem, "[", "]");
        if (!trademsg.size()) {
          break;
        }
        string_view trdpx;
        string_view trdqt;
        string_view vendortime;
        string_view side;
        tie(trdpx, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(trdpx.size(), error, false, "could not parse message",
                            in);
        tie(trdqt, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(trdqt.size(), error, false, "could not parse message",
                            in);
        tie(vendortime, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(vendortime.size(), error, false, "could not parse message",
                            in);
        tie(side, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(side.size(), error, false, "could not parse message",
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
                      string_view(side == "b" ? "b" : "a"));

      }

      return *error == nullptr;
    };
    return {outsv, parse_kraken_trade};
  }
  RETURN_ERROR(error, none, "unknown Kraken stream type", feedtype);
}
