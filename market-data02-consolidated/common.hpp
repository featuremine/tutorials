/******************************************************************************
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
 *****************************************************************************/

#pragma once

#include <string_view>
#include <tuple>

#include <fmc++/serialization.hpp>
#include <fmc++/error.hpp>
#include <fmc/error.h>

using namespace std;

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
