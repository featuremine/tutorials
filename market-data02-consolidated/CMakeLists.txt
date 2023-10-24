#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

add_library(
    feed_handler
    SHARED
    "feed-handler.cpp"
    "binance.cpp"
    "kraken.cpp"
)
target_link_libraries(
    feed_handler
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)
set_target_properties(
    feed_handler
    PROPERTIES
    LIBRARY_OUTPUT_NAME "feed_handler"
    PREFIX ""
)

add_library(
    feed_parser
    SHARED
    "feed-parser.cpp"
)
target_link_libraries(
    feed_parser
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)
set_target_properties(
    feed_parser
    PROPERTIES
    LIBRARY_OUTPUT_NAME "feed_parser"
    PREFIX ""
)
