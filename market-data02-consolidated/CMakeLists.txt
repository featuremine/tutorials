#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

add_executable(
    feed-handler
    "feed-handler.cpp"
)
target_link_libraries(
    feed-handler
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)

#add_executable(
#    feed-parser
#    "feed-parser.cpp"
#)
#target_link_libraries(
#    feed-parser
#    PRIVATE
#    websockets ${LIBWEBSOCKETS_DEP_LIBS}
#    fmc++ ytp
#)
