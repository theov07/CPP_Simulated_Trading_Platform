#include "MatchingEngine.hpp"

#include <algorithm>

MatchingEngine::MatchingEngine(OrderBook& book)
    : book_(book) {}

bool MatchingEngine::can_fully_fill(const Order& order) const {
    int remaining = order.quantity;

    if (order.side == Side::Bid) {
        for (const auto& ask : book_.asks()) {
            const bool eligible =
                (order.type == OrderType::Market) || (ask.price <= order.price);

            if (!eligible) {
                break;
            }

            remaining -= ask.quantity;
            if (remaining <= 0) {
                return true;
            }
        }
        return false;
    }

    for (const auto& bid : book_.bids()) {
        const bool eligible =
            (order.type == OrderType::Market) || (bid.price >= order.price);

        if (!eligible) {
            break;
        }

        remaining -= bid.quantity;
        if (remaining <= 0) {
            return true;
        }
    }

    return false;
}

std::vector<Trade> MatchingEngine::match(const Order& order) {
    std::vector<Trade> trades;

    if (order.quantity <= 0) {
        throw std::runtime_error("Strategy order must have positive quantity");
    }

    if (!can_fully_fill(order)) {
        return trades; // All-or-nothing: order rejected.
    }

    int remaining = order.quantity;
    double last_exec_price = 0.0;
    int total_exec_qty = 0;

    if (order.side == Side::Bid) {
        auto& asks = book_.asks_mutable();

        std::size_t i = 0;
        while (i < asks.size() && remaining > 0) {
            const bool eligible =
                (order.type == OrderType::Market) || (asks[i].price <= order.price);

            if (!eligible) {
                break;
            }

            const int exec_qty = std::min(remaining, asks[i].quantity);
            last_exec_price = asks[i].price;
            total_exec_qty += exec_qty;

            trades.push_back(Trade{
                next_trade_id_++,
                order.timestamp,
                asks[i].order_id,
                order.order_id,
                order.side,
                asks[i].price,
                exec_qty,
                order.strategy_name
            });

            remaining -= exec_qty;
            asks[i].quantity -= exec_qty;

            if (asks[i].quantity == 0) {
                book_.mark_order_inactive(asks[i].order_id);
                asks.erase(asks.begin() + static_cast<long>(i));
            } else {
                ++i;
            }
        }
    } else {
        auto& bids = book_.bids_mutable();

        std::size_t i = 0;
        while (i < bids.size() && remaining > 0) {
            const bool eligible =
                (order.type == OrderType::Market) || (bids[i].price >= order.price);

            if (!eligible) {
                break;
            }

            const int exec_qty = std::min(remaining, bids[i].quantity);
            last_exec_price = bids[i].price;
            total_exec_qty += exec_qty;

            trades.push_back(Trade{
                next_trade_id_++,
                order.timestamp,
                bids[i].order_id,
                order.order_id,
                order.side,
                bids[i].price,
                exec_qty,
                order.strategy_name
            });

            remaining -= exec_qty;
            bids[i].quantity -= exec_qty;

            if (bids[i].quantity == 0) {
                book_.mark_order_inactive(bids[i].order_id);
                bids.erase(bids.begin() + static_cast<long>(i));
            } else {
                ++i;
            }
        }
    }

    if (!trades.empty()) {
        book_.set_last_trade(last_exec_price, total_exec_qty);
    }

    return trades;
}
