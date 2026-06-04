#include "OrderBook.hpp"

#include <algorithm>
#include <iostream>
#include <iomanip>

void OrderBook::sort_books() {
    std::sort(bids_.begin(), bids_.end(), [](const RestingOrder& a, const RestingOrder& b) {
        if (a.price != b.price) {
            return a.price > b.price;
        }
        return a.timestamp < b.timestamp;
    });

    std::sort(asks_.begin(), asks_.end(), [](const RestingOrder& a, const RestingOrder& b) {
        if (a.price != b.price) {
            return a.price < b.price;
        }
        return a.timestamp < b.timestamp;
    });
}

void OrderBook::match_crossing_feed_order(RestingOrder& incoming) {
    auto& opposite_book = (incoming.side == Side::Bid) ? asks_ : bids_;
    const auto crosses = [&incoming](const RestingOrder& resting) {
        if (incoming.side == Side::Bid) {
            return incoming.price >= resting.price;
        }
        return incoming.price <= resting.price;
    };

    double last_exec_price = 0.0;
    std::int64_t total_exec_qty = 0;

    while (incoming.quantity > 0 && !opposite_book.empty() && crosses(opposite_book.front())) {
        RestingOrder& resting = opposite_book.front();
        const int exec_qty = std::min(incoming.quantity, resting.quantity);

        last_exec_price = resting.price;
        total_exec_qty += exec_qty;
        incoming.quantity -= exec_qty;
        resting.quantity -= exec_qty;

        if (resting.quantity == 0) {
            mark_order_inactive(resting.order_id);
            opposite_book.erase(opposite_book.begin());
        }
    }

    if (total_exec_qty > 0) {
        set_last_trade(last_exec_price, total_exec_qty);
    }
}

void OrderBook::on_add(const OrderAdd& event) {
    if (seen_order_ids_.count(event.order_id) > 0) {
        throw std::runtime_error("Duplicate order_id in OrderBook: " + std::to_string(event.order_id));
    }
    seen_order_ids_.insert(event.order_id);

    RestingOrder ro;
    ro.order_id = event.order_id;
    ro.timestamp = event.timestamp;
    ro.side = event.side;
    ro.price = event.price;
    ro.quantity = event.quantity;

    match_crossing_feed_order(ro);
    if (ro.quantity == 0) {
        mark_order_inactive(ro.order_id);
        return;
    }

    if (ro.side == Side::Bid) {
        bids_.push_back(ro);
    } else {
        asks_.push_back(ro);
    }

    sort_books();
}

void OrderBook::on_remove(const OrderRemove& event) {
    auto remove_id = [id = event.order_id](std::vector<RestingOrder>& book) {
        auto it = std::remove_if(book.begin(), book.end(), [id](const RestingOrder& o) {
            return o.order_id == id;
        });
        const bool removed = (it != book.end());
        book.erase(it, book.end());
        return removed;
    };

    const bool removed_bid = remove_id(bids_);
    const bool removed_ask = remove_id(asks_);

    if (removed_bid || removed_ask) {
        mark_order_inactive(event.order_id);
        return;
    }

    if (inactive_order_ids_.count(event.order_id) > 0) {
        return;
    }

    if (seen_order_ids_.count(event.order_id) == 0) {
        std::cout << "[ORDERBOOK][WARN] REMOVE ignored for unknown order_id="
                  << event.order_id << "\n";
    }
}

double OrderBook::best_bid() const {
    if (bids_.empty()) {
        return 0.0;
    }
    return bids_.front().price;
}

double OrderBook::best_ask() const {
    if (asks_.empty()) {
        return 0.0;
    }
    return asks_.front().price;
}

double OrderBook::spread() const {
    if (bids_.empty() || asks_.empty()) {
        return 0.0;
    }
    return best_ask() - best_bid();
}

MarketData OrderBook::snapshot(std::int64_t ts) const {
    MarketData md;
    md.timestamp = ts;
    md.best_bid = best_bid();
    md.best_ask = best_ask();

    if (last_trade_price_ > 0.0) {
        md.last_price = last_trade_price_;
    } else if (md.best_bid > 0.0 && md.best_ask > 0.0) {
        md.last_price = 0.5 * (md.best_bid + md.best_ask);
    } else {
        md.last_price = 0.0;
    }

    md.volume = last_trade_volume_;
    return md;
}

void OrderBook::display(int levels) const {
    std::cout << "\n========== ORDER BOOK ==========\n";
    std::cout << "ASKS\n";
    const int ask_levels = std::min<int>(levels, static_cast<int>(asks_.size()));
    for (int i = ask_levels - 1; i >= 0; --i) {
        std::cout << std::setw(8) << asks_[i].order_id
                  << " | " << std::setw(10) << std::fixed << std::setprecision(2) << asks_[i].price
                  << " | " << std::setw(6) << asks_[i].quantity << "\n";
    }

    std::cout << "BIDS\n";
    for (int i = 0; i < std::min<int>(levels, static_cast<int>(bids_.size())); ++i) {
        std::cout << std::setw(8) << bids_[i].order_id
                  << " | " << std::setw(10) << std::fixed << std::setprecision(2) << bids_[i].price
                  << " | " << std::setw(6) << bids_[i].quantity << "\n";
    }
    std::cout << "================================\n";
}

const std::vector<RestingOrder>& OrderBook::bids() const {
    return bids_;
}

const std::vector<RestingOrder>& OrderBook::asks() const {
    return asks_;
}

std::vector<RestingOrder>& OrderBook::bids_mutable() {
    return bids_;
}

std::vector<RestingOrder>& OrderBook::asks_mutable() {
    return asks_;
}

void OrderBook::set_last_trade(double price, std::int64_t volume) {
    last_trade_price_ = price;
    last_trade_volume_ = volume;
}

void OrderBook::mark_order_inactive(std::uint64_t order_id) {
    inactive_order_ids_.insert(order_id);
}
