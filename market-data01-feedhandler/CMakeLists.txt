#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

add_executable(
    minimal-ws-client-binance
    "minimal-ws-client-binance.c"
)
target_link_libraries(
    minimal-ws-client-binance
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
)

add_library(
    binance_feed_handler
    SHARED
    "binance-feed-handler.cpp"
)
target_link_libraries(
    binance_feed_handler
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)
set_target_properties(
    binance_feed_handler
    PROPERTIES
    LIBRARY_OUTPUT_NAME "binance_feed_handler"
    PREFIX ""
)
