#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

add_subproject(
    NAME websockets
    VERSION "v4.3.2"
    GIT_REVISION "v4.3.2"
    GIT_URL "https://github.com/warmcat/libwebsockets.git"
    TARGETS websockets
)

add_executable(
    minimal-ws-client-binance
    "minimal-ws-client-binance.c"
)
target_link_libraries(
    minimal-ws-client-binance
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
)