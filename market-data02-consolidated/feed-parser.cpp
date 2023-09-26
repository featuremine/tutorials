/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.

 *****************************************************************************/

#include <ctype.h>
#include <signal.h>
#include <string.h>
#include <stdio.h>

#include <functional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <memory>

#include <fmc/cmdline.h>
#include <fmc/files.h>
#include <fmc/time.h>
#include <ytp/announcement.h>
#include <ytp/data.h>
#include <ytp/streams.h>
#include <ytp/yamal.h>

using namespace std;

// Parser gets the original data, string to write data to
// sequence number processed and error.
// Sets error if could not parse.
// Returns true is processed, false if duplicated.
typedef bool parser_t(string_view, string&, uint64_t*, fmc_error_t**);
typedef pair<string_view, parser_t> resolver_t(string_view, fmc_error_t**);

// This section here is binance parsing code
bool parse_binance_bookTicker(string_view in, string &out, uint64_t *seq, fmc_error_t**error) {

}

bool parse_binance_trade(string_view in, string &out, uint64_t *seq, fmc_error_t**error) {

}

pair<string_view, parser_t>  get_binance_channel_in(string_view sv, fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  if (pos == sv.npos) {
    fmc_error_set(error, "missing @ in the Binance stream name %s", string(sv).c_str());
    return {string_view(), nullptr};
  }
  auto feedtype = sv.substr(pos + 1);
  auto outsv = sv.substr(0, pos);
  if (feedtype == 'bookTicker') {
    return {outsv, parse_binance_bookTicker};
  } else if (feedtype == 'trade') {
    return {outsv, parse_binance_trade};
  }
  fmc_error_set(error, "unknown Binance stream type %s", string(feedtype).c_str());
  return {string_view(), nullptr};
}

static int interrupted = 0;
static void sigint_handler(int sig) { interrupted = 1; }

// If you compiling with C++20 you don't need this
bool starts_with(std::string_view a, string_view b) {
  return a.substr(0, b.size()) == b;
}

struct parser_t {
  // This is where we store information about channel processed
  struct stream_out_t {
    uint64_t count = 0;
    ytp_mmnode_offs stream;
  };

  struct channel_in_t {
    parser_t parser;
    struct stream_out_t *outinfo = nullptr;
    uint64_t seqno = 0ULL;
  };

  void init(fmc_error_t **error);
  void recover(fmc_error_t **error);
  channels_out_t::iterator get_stream_out(string_view sv);
  channels_in_t::iterator get_channel_in(std::string_view sv, fmc_error_t **error);
  stream_out_t *emplace_stream_out(ytp_mmnode_offs stream);

  // We use a hash map to store stream info
  using channels_in_t = unordered_map<string_view, unique_ptr<channel_in_t>>;
  using streams_out_t = unordered_map<ytp_mmnode_offs, unique_ptr<stream_out_t>>;
  using streams_in_t = unordered_map<ytp_mmnode_offs, channel_in_t*>;
  // This map contains a context factory for each supported feed
  unordered_map<string, resolver_t> resolvers = {
    {"binance", get_binance_channel_in}
  };
  channels_in_t chans_in;
  // Hash map to keep track of outgoing streams
  streams_out_t s_out;
  streams_in_t s_in;
  string_view prefix_out = "ore/";
  string_view prefix_in = "raw/";
  const char *peer = nullptr;
  const char *ytp_in = nullptr;
  const char *ytp_out = nullptr;
};

void parser_t::init(fmc_error_t **error) {
  int fd_in = fmc_fopen(ytp_in, fmc_fmode::READ, &error);
  if (error) {
    fmc_error_add(error, "; ", "could not open input yamal file %s", ytp_in);
    return;
  }

  int fd_out = fmc_fopen(ytp_out, fmc_fmode::READWRITE, &error);
  if (error) {
    fmc_error_add(error, "; ", "could not open output yamal file %s", ytp_out);
    return;
  }

  auto *y_in = ytp_yamal_new(fd_in, &error);
  if (error) {
    fmc_error_add(error, "; ", "could not create input yamal");
    return;
  }

  auto *y_out = ytp_yamal_new(fd_out, &error);
  if (error) {
    fmc_error_add(error, "; ", "could not create output yamal");
    return;
  }
  
  auto *streams = ytp_streams_new(y_out, &error);
  if (error) {
    fmc_error_add(error, "; ", "could not create stream");
    return;
  }
}

stream_out_t *parser_t::emplace_stream_out(ytp_mmnode_offs stream)  {
  return s_out.emplace(stream, make_unique<stream_out_t>()).first.second.get();
}

stream_out_t *parser_t::get_stream_out(ytp_mmnode_offs stream, fmc_error_t **error)  {
  auto where = s_out.find(stream);
  // If we never seen this stream, we need to add it to the map of out streams
  // and if we care about this particular channel create info for this channel.
  if (where != s_out.end())
    return where->second.get();

  uint64_t seqno;
  size_t psz, csz, esz;
  const char *peer, *channel, *encoding;
  ytp_mmnode_offs *original, *subscribed;
  // This functions looks up stream announcement details
  ytp_announcement_lookup(mco.yamal, stream, &seqno, &psz, &peer, &csz,
                          &channel, &esz, &encoding, &original, &subscribed,
                          &error);
  if (error) {
    fmc_error_add(error, "; ", "could not look up stream");
    return;
  }
  // if this stream is not one of ours or wrong format, skip
  if (string_view(peer, psz) != pier_sv || !starts_with(string_view{channel, csz}, prefix_out)) {
    return .emplace(stream, nullptr).first.second.get();
  }
  return emplace_stream_out(stream);
}

stream_out_t *parser_t::get_stream_out(string_view sv, fmc_error_t **error)  {
  string chstr = string(prefix_out) + sv;
  auto stream = ytp_streams_announce(
      streams, vpeer.size(), vpeer.data(), chstr.size(), chstr.data(),
      encoding.size(), encoding.data(), &error);
  if (*error)
    return nullptr;
  return emplace_stream_out(stream);
}

channels_in_t::iterator parser_t::get_channel_in(std::string_view sv, fmc_error_t **error) {
  fmc_error_clear(error);

  auto where = chans_in.find(sv);
  if (where != chans_in.end())
    return where;

  auto feed = sv.substr(0, sv.find_first_of('/'));
  
  auto resolver = resolvers.find(feed);
  if (resolver == resolvers.end()) {
    fmc_error_set(error, "unknown feed %s", string(feed).c_str());
    return chans_in.end()
  }
  auto [outsv, parser] = resolver(sv, error);
  if (*error)
    return;
  
  auto *outinfo = get_stream_out(outsv, error);
  if (*error)
    return;

  return chans_in.emplace(sv, channel_in_t{.parser = parser; .outinfo = outinfo}).first;
}

void parser_t::recover(fmc_error_t **error) {
  // This is where we do recovery. We count the number of messages we written for each channel.
  // Then we skip the correct number of messages for each channel from the input to recover
  string_view pier_sv = peer;
  auto it_out = ytp_data_begin(y_out, error);
  for (; !ytp_yamal_term(it_out) && !interrupted; it_out = ytp_yamal_next(ytp_in, it_out, error);) {
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
    if (error) {
      fmc_error_add(error, "; ", "could not read data");
      return;
    }
    auto *chan = get_stream_out(stream, error);
    if (error) {
      fmc_error_add(error, "; ", "could not find output stream");
      return;
    }
    if (!chan)
      continue;
    ++chan->count;
  }
}

void parser_t::run(fmc_error_t **error) {
  auto it_in = ytp_data_begin(y_in, &error);
  while (!interrupted) {
    for (; !ytp_yamal_term(it_in); it_in = ytp_yamal_next(ytp_in, it_in, &error);) {
      if (error) {
        fprintf(stderr, "could not obtain iterator with error %s\n", fmc_error_msg(error));
        return 1; 
      }
      uint64_t seqno;
      int64_t ts;
      ytp_mmnode_offs stream;
      size_t sz;
      const char *data;
      ytp_data_read(ytp_in, it_in, &seqno, &ts, &stream, &sz, &data, &error);
      if (error) {
        fprintf(stderr, "could not read data with error %s\n", fmc_error_msg(error));
        return 1; 
      }
      // Look up the stream in the input stream map
      auto where = s_in.find(stream);
      // if we don't know this input stream, look up stream info,
      // check if it is one of ours, if not check it starts with
      // correct prefix. If so, add this to the channel map
      if (where == s_in.end()) {
        uint64_t seqno;
        size_t psz, csz, esz;
        const char *peer, *channel, *encoding;
        ytp_mmnode_offs *original, *subscribed;
        // This functions looks up stream announcement details
        ytp_announcement_lookup(mco.yamal, stream, &seqno, &psz, &peer, &csz,
                                &channel, &esz, &encoding, &original, &subscribed,
                                &error);
        if (error) {
          fprintf(stderr, "could not look up stream with error %s\n", fmc_error_msg(error));
          return 1;
        }
        string_view channel_sv{channel, csz};
        // if this stream is one of ours or wrong format, skip
        if (string_view(peer, psz) == pier_sv || !starts_with(channel_sv, prefix_in)) {
          s_in.emplace(stream, nullptr);
          continue;
        }
        // we remove the prefix from the input channel name
        string_view channel_sv = channel_sv.substr(prefix_in.size());

        // get up the input channel
        auto channel_it = get_input_channel_info(channel_sv, &error);
        if (channel_it == chans_out.end()) {
          cerr << "could not create output channel for stream " << channel_sv
               << " with error " << fmc_error_msg(error) << endl;
          s_in.emplace(stream, nullptr);
          continue;
        }
        where = s_in.emplace(stream, channel_it->second.get()).first;
      }
      // if this channel not interesting, skip it
      if (!where->second)
        continue;
      // otherwise check if we still recovering
      auto *info = where->second;
      if (info->outinfo->count) {
        --info->outinfo->count;
        continue;
      }
      // parse the actual data and write it to the output stream
    }
  }
}

int main(int argc, const char **argv) {
  using namespace std;

  fmc_error_t *error = nullptr;

  // set up signal handler
  signal(SIGINT, sigint_handler);

  parser_t parser;

  // command line option processing
  fmc_cmdline_opt_t options[] = {/* 0 */ {"--help", false, NULL},
                                 /* 1 */ {"--peer", true, &parser.peer},
                                 /* 1 */ {"--ytp-input", true, &parser.ytp_in},
                                 /* 2 */ {"--ytp-output", true, &parser.ytp_out},
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

  parser.init(&error);
  if (error) {
    fprintf(stderr, "could not initialize with error: %s\n", fmc_error_msg(error));
    return 1;
  }

  parser.recover(&error);
  if (error) {
    fprintf(stderr, "could not recover with error: %s\n", fmc_error_msg(error));
    return 1;
  }

  parser.run(&error);
  if (error) {
    fprintf(stderr, "run-time error: %s\n", fmc_error_msg(error));
    return 1;
  }

  return 0;
}
