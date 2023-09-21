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

static int interrupted = 0;
static void sigint_handler(int sig) { interrupted = 1; }

// This is where we store information about channel processed
struct channel_out_t
{
  uint64_t count = 0;
  ytp_mmnode_offs stream;
};

struct channel_in_t
{
  struct channel_out_t *outinfo = nullptr;
  std::function<bool(string_view, string&)> parser;
};

// If you compiling with C++20 you don't need this
bool starts_with(std::string_view a, string_view b) {
  return a.substr(0, b.size()) == b;
}

// We use a hash map to store stream info
using channels_out_t = unordered_map<string_view, unique_ptr<channel_out_t>>;
using channels_in_t = unordered_map<string_view, unique_ptr<channel_in_t>>;
using streams_out_t = unordered_map<ytp_mmnode_offs, channel_out_t*>;
using streams_in_t = unordered_map<ytp_mmnode_offs, channel_in_t*>;
using info_in_getter_t = function(streams_in_t::iterator(std::string_view, fmc_error_t);
channels_out_t chans_out;
channels_in_t chans_in;
// Hash map to keep track of outgoing streams
streams_out_t s_out;
streams_in_t s_in;
string_view prefix_out = "ore/";
string_view prefix_in = "raw/";

channels_in_t::iterator get_binance_channel_in(std::string_view sv, fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  if (pos == sv.npos) {
    fmc_error_set(error, "missing @ in the Binance stream name %s", string(sv).c_str());
    return chans_in.end();
  }
  return
  auto feedtype = sv.substr();
}

unordered_map<string,  info_in_getter_t> gens_in = {
  {"binance", get_binance_channel_in}
};

channels_in_t::iterator get_channel_in(std::string_view sv, fmc_error_t **error) {
  fmc_error_clear(error);

  auto where = chans_in.find(sv);
  if (where != chans_in.end())
    return where;

  auto feed = sv.substr(0, sv.find_first_of('/'));
  
  auto gen = gens_in.find(feed);
  if (gen == gens_in.end()) {
    fmc_error_set(error, "unknown feed %s", string(feed).c_str());
    return chans_in.end()
  }
  return gen(sv, error);
}


int main(int argc, const char **argv) {
  using namespace std;

  fmc_error_t *error = nullptr;

  // set up signal handler
  signal(SIGINT, sigint_handler);

  // command line option processing
  const char *peer = nullptr;
  const char *ytp_in = nullptr;
  const char *ytp_out = nullptr;
  fmc_cmdline_opt_t options[] = {/* 0 */ {"--help", false, NULL},
                                 /* 1 */ {"--peer", true, &peer},
                                 /* 1 */ {"--ytp-input", true, &ytp_in},
                                 /* 2 */ {"--ytp-output", true, &ytp_out},
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

  int fd_in = fmc_fopen(ytp_in, fmc_fmode::READ, &error);
  if (error) {
    fprintf(stderr, "could not open input yamal file %s with error %s\n", ytp_in, fmc_error_msg(error));
    return 1;
  }

  int fd_out = fmc_fopen(ytp_out, fmc_fmode::READWRITE, &error);
  if (error) {
    fprintf(stderr, "could not open output yamal file %s with error %s\n", ytp_out, fmc_error_msg(error));
    return 1;
  }

  auto *y_in = ytp_yamal_new(fd_in, &error);
  if (error) {
    fprintf(stderr, "could not create input yamal with error %s\n", fmc_error_msg(error));
    return 1;
  }

  auto *y_out = ytp_yamal_new(fd_out, &error);
  if (error) {
    fprintf(stderr, "could not create output yamal with error %s\n", fmc_error_msg(error));
    return 1;
  }
  
  auto *streams = ytp_streams_new(y_out, &error);
  if (error) {
    fprintf(stderr, "could not create stream with error %s\n", fmc_error_msg(error));
    return 1;
  }

  string_view pier_sv = peer;

  // This is where we do recovery. We count the number of messages we written for each channel.
  // Then we skip the correct number of messages for each channel from the input to recover
  auto it_out = ytp_data_begin(y_out, &error);
  for (; !ytp_yamal_term(it_out) && !interrupted; it_out = ytp_yamal_next(ytp_in, it_out, &error);) {
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
    auto where = s_out.find(stream);
    // If we never seen this stream, we need to add it to the map of out streams
    // and if we care about this particular channel create info for this channel.
    if (where == s_out.end()) {
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
      // if this stream is not one of ours or wrong format, skip
      if (string_view(peer, psz) != pier_sv || !starts_with(channel_sv, prefix_out)) {
        s_out.emplace(stream, nullptr);
        continue;
      }
      auto *info = new channel_out_t();
      auto chview = string_view(channel, csz).substr(prefix.size());
      chans_out[channel_sv.substr(prefix_out.size())].reset(info);
      where = s_out.emplace(stream, info).first;
    }
    if (!where->second)
      continue;
    ++where->second->count;
  }

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

  return 0;
}
