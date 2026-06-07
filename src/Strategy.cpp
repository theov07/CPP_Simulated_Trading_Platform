#include "Strategy.hpp"

#include <cmath>
#include <stdexcept>
#include <algorithm>

MomentumStrategy::MomentumStrategy(std::size_t fast_window,
                                   std::size_t slow_window,
                                   double epsilon,
                                   int qty,
                                   OrderType type)
    : fast_(fast_window),
      slow_(slow_window),
      epsilon_(epsilon),
      qty_(qty),
      type_(type) {
    if (fast_window >= slow_window) {
        throw std::runtime_error("MomentumStrategy requires fast_window < slow_window");
    }
}

Signal MomentumStrategy::on_market_data(const MarketData& data) {
    if (data.last_price <= 0.0) {
        return Signal::Hold;
    }

    fast_.push(data.last_price);
    slow_.push(data.last_price);

    if (!fast_.full() || !slow_.full()) {
        return Signal::Hold;
    }

    const double fast_ma = fast_.mean();
    const double slow_ma = slow_.mean();

    if (fast_ma > slow_ma + epsilon_) {
        return Signal::Buy;
    }
    if (fast_ma < slow_ma - epsilon_) {
        return Signal::Sell;
    }

    return Signal::Hold;
}

std::string MomentumStrategy::name() const {
    return "MomentumStrategy";
}

OrderType MomentumStrategy::preferred_order_type() const {
    return type_;
}

int MomentumStrategy::quantity() const {
    return qty_;
}

MeanReversionStrategy::MeanReversionStrategy(std::size_t window,
                                             double z_threshold,
                                             int qty,
                                             OrderType type)
    : prices_(window),
      z_threshold_(z_threshold),
      qty_(qty),
      type_(type) {}

Signal MeanReversionStrategy::on_market_data(const MarketData& data) {
    if (data.last_price <= 0.0) {
        return Signal::Hold;
    }

    prices_.push(data.last_price);

    if (!prices_.full()) {
        return Signal::Hold;
    }

    const double m = prices_.mean();
    const double s = prices_.stddev();

    if (s <= 1e-12) {
        return Signal::Hold;
    }

    const double z = (data.last_price - m) / s;

    if (z > z_threshold_) {
        return Signal::Sell;
    }
    if (z < -z_threshold_) {
        return Signal::Buy;
    }

    return Signal::Hold;
}

std::string MeanReversionStrategy::name() const {
    return "MeanReversionStrategy";
}

OrderType MeanReversionStrategy::preferred_order_type() const {
    return type_;
}

int MeanReversionStrategy::quantity() const {
    return qty_;
}

std::unique_ptr<Strategy> make_strategy(const std::string& strategy_name) {
    std::string s = strategy_name;
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });

    if (s == "momentum") {
        return std::make_unique<MomentumStrategy>(
            2,          // fast window
            3,          // slow window
            0.001,      // very small epsilon
            2,          // qty
            OrderType::Market
        );
    }

    if (s == "mean_reversion" || s == "meanreversion" || s == "mr") {
        return std::make_unique<MeanReversionStrategy>(
            4,          // rolling window
            0.3,        // very low threshold
            2,          // qty
            OrderType::Market
        );
    }

    if (s == "bollinger") {
        return std::make_unique<BollingerBandsStrategy>(
            4,
            0.8,
            2,
            OrderType::Market
        );
    }

    if (s == "ma_cross" || s == "moving_average_cross") {
        return std::make_unique<MovingAverageCrossStrategy>(
            3,
            7,
            2,
            OrderType::Market
        );
    }

    throw std::runtime_error("Unknown strategy: " + strategy_name);
}

BollingerBandsStrategy::BollingerBandsStrategy(std::size_t window,
                                               double num_stddev,
                                               int qty,
                                               OrderType type)
    : prices_(window), num_stddev_(num_stddev), qty_(qty), type_(type) {}

Signal BollingerBandsStrategy::on_market_data(const MarketData& data) {
    if (data.last_price <= 0.0) {
        return Signal::Hold;
    }

    prices_.push(data.last_price);
    if (!prices_.full()) {
        return Signal::Hold;
    }

    const double m = prices_.mean();
    const double s = prices_.stddev();
    const double upper = m + num_stddev_ * s;
    const double lower = m - num_stddev_ * s;

    if (data.last_price > upper) {
        return Signal::Sell;
    }
    if (data.last_price < lower) {
        return Signal::Buy;
    }
    return Signal::Hold;
}

std::string BollingerBandsStrategy::name() const {
    return "BollingerBandsStrategy";
}

OrderType BollingerBandsStrategy::preferred_order_type() const {
    return type_;
}

int BollingerBandsStrategy::quantity() const {
    return qty_;
}

MovingAverageCrossStrategy::MovingAverageCrossStrategy(std::size_t fast_window,
                                                       std::size_t slow_window,
                                                       int qty,
                                                       OrderType type)
    : fast_(fast_window), slow_(slow_window), qty_(qty), type_(type) {}

Signal MovingAverageCrossStrategy::on_market_data(const MarketData& data) {
    if (data.last_price <= 0.0) {
        return Signal::Hold;
    }

    fast_.push(data.last_price);
    slow_.push(data.last_price);

    if (!fast_.full() || !slow_.full()) {
        return Signal::Hold;
    }

    const double fast_ma = fast_.mean();
    const double slow_ma = slow_.mean();

    if (fast_ma > slow_ma) {
        return Signal::Buy;
    }
    if (fast_ma < slow_ma) {
        return Signal::Sell;
    }
    return Signal::Hold;
}

std::string MovingAverageCrossStrategy::name() const {
    return "MovingAverageCrossStrategy";
}

OrderType MovingAverageCrossStrategy::preferred_order_type() const {
    return type_;
}

int MovingAverageCrossStrategy::quantity() const {
    return qty_;
}
