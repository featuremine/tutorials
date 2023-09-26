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
typedef bool (*parser_t)(string_view, string&, uint64_t*, fmc_error_t**);
typedef pair<string_view, parser_t> (*resolver_t)(string_view, fmc_error_t**);

// This section here is binance parsing code
bool parse_binance_bookTicker(string_view in, string &out, uint64_t *seq, fmc_error_t**error) {
  ++(*seq);
  out.append(in.data(), in.size());
  return true;
}

bool parse_binance_trade(string_view in, string &out, uint64_t *seq, fmc_error_t**error) {
  ++(*seq);
  out.append(in.data(), in.size());
  return true;
}

pair<string_view, parser_t>  get_binance_channel_in(string_view sv, fmc_error_t **error) {
  auto pos = sv.find_last_of('@');
  if (pos == sv.npos) {
    fmc_error_set(error, "missing @ in the Binance stream name %s", string(sv).c_str());
    return {string_view(), nullptr};
  }
  auto feedtype = sv.substr(pos + 1);
  auto outsv = sv.substr(0, pos);
  if (feedtype == "bookTicker") {
    return {outsv, parse_binance_bookTicker};
  } else if (feedtype == "trade") {
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
  using streams_out_t = unordered_map<ytp_mmnode_offs, unique_ptr<stream_out_t>>;
  using streams_in_t = unordered_map<ytp_mmnode_offs, stream_in_t>;
  // This map contains a context factory for each supported feed
  unordered_map<string, resolver_t> resolvers = {
    {"binance", get_binance_channel_in}
  };
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
    fmc_error_add(error, "; ", "could not open input yamal file %s", ytp_file_in);
    return;
  }

  fd_out = fmc_fopen(ytp_file_out, fmc_fmode::READWRITE, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not open output yamal file %s", ytp_file_out);
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
  // This is where we do recovery. We count the number of messages we written for each channel.
  // Then we skip the correct number of messages for each channel from the input to recover
  auto it_out = ytp_data_begin(ytp_out, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not obtain iterator");
    return; 
  }
  for (; !ytp_yamal_term(it_out) && !interrupted; it_out = ytp_yamal_next(ytp_in, it_out, error)) {
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
  string buf;
  auto it_in = ytp_data_begin(ytp_in, error);
  if (*error) {
    fmc_error_add(error, "; ", "could not obtain iterator");
    return; 
  }
  while (!interrupted) {
    for (; !ytp_yamal_term(it_in); it_in = ytp_yamal_next(ytp_in, it_in, error)) {
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
      buf.resize(0);
      seqno = info->seqno;
      bool res = info->parser(string_view(data, sz), buf, &seqno, error);
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
      auto dst = ytp_data_reserve(ytp_out, buf.size(), error);
      if (*error) {
        fmc_error_add(error, "; ", "could not reserve message");
        return; 
      }
      memcpy(dst, buf.data(), buf.size());
      ytp_data_commit(ytp_out, fmc_cur_time_ns(), info->outinfo->stream, dst, error);
      if (*error) {
        fmc_error_add(error, "; ", "could not commit message");
        return; 
      }
    }
  }
}

runner_t::stream_out_t *runner_t::emplace_stream_out(ytp_mmnode_offs stream)  {
  return s_out.emplace(stream, make_unique<stream_out_t>(stream_out_t{stream, 0ULL})).first->second.get();
}

runner_t::stream_out_t *runner_t::get_stream_out(ytp_mmnode_offs stream, fmc_error_t **error)  {
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
  if (string_view(origpeer, psz) != peer || !starts_with(string_view{channel, csz}, prefix_out)) {
    return s_out.emplace(stream, nullptr).first->second.get();
  }
  return emplace_stream_out(stream);
}

runner_t::stream_out_t *runner_t::get_stream_out(string_view sv, fmc_error_t **error)  {
  auto vpeer = string_view(peer);
  string chstr;
  chstr.append(prefix_out);
  chstr.append(sv);
  auto stream = ytp_streams_announce(
      streams, vpeer.size(), vpeer.data(), chstr.size(), chstr.data(),
      encoding.size(), encoding.data(), error);
  if (*error) {
    fmc_error_add(error, "; ", "could not announce stream");
    return nullptr;
  }
  return emplace_stream_out(stream);
}

runner_t::stream_in_t *runner_t::get_stream_in(ytp_mmnode_offs stream, fmc_error_t **error) {
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
    return &s_in.emplace(stream, stream_in_t{nullptr}).first->second;
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
  return &s_in.emplace(stream, stream_in_t{.parser=parser, .outinfo=outinfo}).first->second;
}

int main(int argc, const char **argv) {
  using namespace std;

  fmc_error_t *error = nullptr;

  // set up signal handler
  signal(SIGINT, sigint_handler);

  runner_t runner;

  // command line option processing
  fmc_cmdline_opt_t options[] = {/* 0 */ {"--help", false, NULL},
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
    fprintf(stderr, "could not initialize with error: %s\n", fmc_error_msg(error));
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
