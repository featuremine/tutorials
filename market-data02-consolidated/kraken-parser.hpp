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

#include "common.hpp"
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
    // This section here is kraken parsing code
    auto parse_kraken_spread =
        [ctx = kraken_parse_ctx{}](string_view in, cmp_str_t *cmp, int64_t tm,
                                   uint64_t *last, bool skip,
                                   fmc_error_t **error) mutable {
          *last = tm;
          std::string_view bidpx;
          std::string_view bidqt;
          std::string_view askpx;
          std::string_view askqt;
          std::string_view ts;
          std::string_view rem;
          tie(bidpx, rem) = simple_json_parse(in, "\"", "\"");
          RETURN_ERROR_UNLESS(bidpx.size(), error, false,
                              "could not parse message", in);
          tie(askpx, rem) = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(askpx.size(), error, false,
                              "could not parse message", in);
          tie(ts, rem) = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(ts.size(), error, false,
                              "could not parse message", in);
          tie(bidqt, rem) = simple_json_parse(rem, "\"", "\"");
          RETURN_ERROR_UNLESS(bidqt.size(), error, false,
                              "could not parse message", in);
          tie(askqt, rem) = simple_json_parse(rem, "\"", "\"");
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
                          (uint64_t)*last,
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
                          (uint64_t)*last,
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
                          (uint64_t)*last,
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
                          (uint64_t)*last,
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
                          (uint64_t)*last,
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
                          (uint64_t)*last,
                          (uint8_t)0,           // batch (last batch message)
                          (int32_t)chanid,      // imnt_id
                          (int32_t)(chanid + 1) // order_id
            );
          }

          return *error == nullptr;
        };
    return {outsv, parse_kraken_spread};
  } else if (feedtype == "trade") {
    auto parse_kraken_trade = [ocurrence = 0](string_view in, cmp_str_t *cmp,
                                              int64_t tm, uint64_t *last,
                                              bool skip,
                                              fmc_error_t **error) mutable {
      auto trades_pos = in.find("[", 1);
      RETURN_ERROR_UNLESS(trades_pos != std::string_view::npos, error, false,
                          "Invalid trade message", in);
      auto first_trade_pos = in.find("[", trades_pos);
      RETURN_ERROR_UNLESS(first_trade_pos != std::string_view::npos, error,
                          false, "Invalid trade message", in);
      auto rem = in.substr(first_trade_pos);
      std::string_view trademsg;
      uint64_t seqno = 0;
      while (true) {
        tie(trademsg, rem) = simple_json_parse(rem, "[", "]");
        if (!trademsg.size()) {
          break;
        }
        string_view trdpx;
        string_view trdqt;
        string_view vendorsecs;
        string_view vendorus;
        string_view side;
        string_view tmp;
        tie(trdpx, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(trdpx.size(), error, false,
                            "could not parse trade price in message", in);
        tie(trdqt, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(trdqt.size(), error, false,
                            "could not parse trade quantity in message", in);
        tie(vendorsecs, tmp) = simple_json_parse(trademsg, "\"", ".");
        RETURN_ERROR_UNLESS(vendorsecs.size(), error, false,
                            "could not parse vendor seconds price in message",
                            in);
        auto [vendor_s, parsed_s] = fmc::from_string_view<uint64_t>(vendorsecs);
        RETURN_ERROR_UNLESS(vendorsecs.size() == parsed_s.size(), error, false,
                            "could not parse integer from seconds in message",
                            in);
        tie(vendorus, trademsg) = simple_json_parse(trademsg, ".", "\"");
        RETURN_ERROR_UNLESS(vendorus.size(), error, false,
                            "could not parse vendor microseconds in message",
                            in);
        auto [vendor_us, parsed_us] =
            fmc::from_string_view<uint64_t>(vendorsecs);
        RETURN_ERROR_UNLESS(
            vendorsecs.size() == parsed_us.size(), error, false,
            "could not parse integer from microseconds in message", in);
        auto vendor_ns = vendor_s * 1000000000ULL + vendor_us * 1000ULL;
        if (seqno == 0) {
          ocurrence += *last == vendor_ns;
          ocurrence *= *last == vendor_ns;
          seqno = vendor_ns + ocurrence;
          *last = vendor_ns;
        }

        tie(side, trademsg) = simple_json_parse(trademsg, "\"", "\"");
        RETURN_ERROR_UNLESS(side.size(), error, false,
                            "could not parse side in message", in);

        // ORE Off Book Trade Message
        // [11, receive, vendor offset, vendor seqno, batch, imnt id, trade
        // price, qty, decorator]
        cmp_ore_write(cmp, error,
                      (uint8_t)11,               // Message Type ID
                      (int64_t)tm,               // receive
                      (int64_t)(tm - vendor_ns), // vendor offset in ns
                      (uint64_t)seqno,           // vendor seqno
                      (uint8_t)0,                // batch
                      (uint64_t)chanid,          // imnt_id
                      trdpx,                     // trade price
                      trdqt,                     // qty
                      string_view(side == "b" ? "b" : "a"));
      }

      return *error == nullptr;
    };
    return {outsv, parse_kraken_trade};
  }
  RETURN_ERROR(error, none, "unknown Kraken stream type", feedtype);
}
