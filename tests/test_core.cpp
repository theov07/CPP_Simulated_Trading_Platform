#include "MarketDataFeed.hpp"
#include "MatchingEngine.hpp"
#include "OrderBook.hpp"
#include "Portfolio.hpp"
#include "RiskMetrics.hpp"
#include "Strategy.hpp"
#include "StrategyEngine.hpp"
#include "Types.hpp"

#include <gtest/gtest.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

namespace {
std::filesystem::path write_temp_csv(const std::string& name, const std::string& content) {
    const auto path = std::filesystem::temp_directory_path() / name;
    std::ofstream file(path);
    file << content;
    return path;
}

class FixedSignalStrategy : public Strategy {
public:
    FixedSignalStrategy(Signal signal, OrderType type, int qty)
        : signal_(signal), type_(type), qty_(qty) {}

    Signal on_market_data(const MarketData&) override {
        return signal_;
    }

    std::string name() const override {
        return "FixedSignalStrategy";
    }

    OrderType preferred_order_type() const override {
        return type_;
    }

    int quantity() const override {
        return qty_;
    }

private:
    Signal signal_;
    OrderType type_;
    int qty_;
};
}

TEST(TypesTest, TrimHandlesEmptyStrings) {
    EXPECT_TRUE(trim("").empty());
    EXPECT_TRUE(trim("   ").empty());
    EXPECT_EQ(trim("\t abc \n"), "abc");
}

TEST(MarketDataFeedTest, ParsesAddAndRemove) {
    const auto path = write_temp_csv(
        "trading_feed_valid.csv",
        "timestamp,event_type,order_id,side,price,quantity\n"
        "1700000001,ADD,1001,BID,100.50,3\n"
        "1700000002,REMOVE,1001,,,\n"
    );

    {
        MarketDataFeed feed(path.string());
        ASSERT_TRUE(feed.has_next());

        const FeedEvent first = feed.next_event();
        const auto& add = std::get<OrderAdd>(first);
        EXPECT_EQ(add.timestamp, 1700000001);
        EXPECT_EQ(add.order_id, 1001u);
        EXPECT_EQ(add.side, Side::Bid);
        EXPECT_DOUBLE_EQ(add.price, 100.50);
        EXPECT_EQ(add.quantity, 3);

        ASSERT_TRUE(feed.has_next());
        const FeedEvent second = feed.next_event();
        const auto& remove = std::get<OrderRemove>(second);
        EXPECT_EQ(remove.timestamp, 1700000002);
        EXPECT_EQ(remove.order_id, 1001u);
    }  // sur windows on peut pas remove tant que ifstream est ouvert 

    std::filesystem::remove(path);
}

TEST(MarketDataFeedTest, ReportsBadNumbers) {
    const auto path = write_temp_csv(
        "trading_feed_invalid.csv",
        "timestamp,event_type,order_id,side,price,quantity\n"
        "1700000001,ADD,1001,ASK,not_a_price,3\n"
    );

    {
        MarketDataFeed feed(path.string());
        EXPECT_THROW(
            {
                try {
                    static_cast<void>(feed.next_event());
                } catch (const std::runtime_error& ex) {
                    EXPECT_NE(std::string(ex.what()).find("Invalid price at CSV line 2"), std::string::npos);
                    throw;
                }
            },
            std::runtime_error
        );
    }  

    std::filesystem::remove(path);
}

TEST(OrderBookTest, MatchesCrossingFeedOrders) {
    OrderBook book;
    book.on_add(OrderAdd{1, 1, Side::Ask, 100.0, 3});
    book.on_add(OrderAdd{2, 2, Side::Bid, 101.0, 5});

    EXPECT_TRUE(book.asks().empty());
    ASSERT_EQ(book.bids().size(), 1u);
    EXPECT_EQ(book.bids().front().order_id, 2u);
    EXPECT_EQ(book.bids().front().quantity, 2);

    MarketData md = book.snapshot(2);
    EXPECT_DOUBLE_EQ(md.last_price, 100.0);
    EXPECT_EQ(md.volume, 3);

    book.on_add(OrderAdd{3, 3, Side::Ask, 102.0, 4});
    EXPECT_DOUBLE_EQ(book.best_bid(), 101.0);
    EXPECT_DOUBLE_EQ(book.best_ask(), 102.0);
    EXPECT_DOUBLE_EQ(book.spread(), 1.0);

    book.on_add(OrderAdd{4, 4, Side::Ask, 100.5, 1});
    ASSERT_FALSE(book.bids().empty());
    EXPECT_EQ(book.bids().front().quantity, 1);
    EXPECT_DOUBLE_EQ(book.best_ask(), 102.0);

    md = book.snapshot(4);
    EXPECT_DOUBLE_EQ(md.last_price, 101.0);
    EXPECT_EQ(md.volume, 1);
}

TEST(MatchingEngineTest, IsAllOrNothing) {
    OrderBook book;
    book.on_add(OrderAdd{1, 1, Side::Ask, 100.0, 1});
    book.on_add(OrderAdd{2, 2, Side::Ask, 101.0, 1});

    MatchingEngine engine(book);
    Order buy{10, 3, Side::Bid, OrderType::Limit, 100.5, 2, "test"};

    auto trades = engine.match(buy);
    EXPECT_TRUE(trades.empty());
    ASSERT_EQ(book.asks().size(), 2u);
    EXPECT_EQ(book.asks()[0].quantity, 1);
    EXPECT_EQ(book.asks()[1].quantity, 1);

    buy.price = 101.0;
    trades = engine.match(buy);
    ASSERT_EQ(trades.size(), 2u);
    const int total_qty = std::accumulate(
        trades.begin(),
        trades.end(),
        0,
        [](int sum, const Trade& trade) { return sum + trade.quantity; }
    );
    EXPECT_EQ(total_qty, 2);
    EXPECT_TRUE(book.asks().empty());

    const MarketData md = book.snapshot(3);
    EXPECT_DOUBLE_EQ(md.last_price, 101.0);
    EXPECT_EQ(md.volume, 2);
}

TEST(OrderBookTest, RemoveAfterExecutionIsSilent) {
    OrderBook book;
    book.on_add(OrderAdd{1, 1, Side::Ask, 100.0, 1});
    book.on_add(OrderAdd{2, 2, Side::Bid, 101.0, 1});

    std::ostringstream captured;
    auto* original = std::cout.rdbuf(captured.rdbuf());
    book.on_remove(OrderRemove{3, 1});
    book.on_remove(OrderRemove{4, 2});
    std::cout.rdbuf(original);

    EXPECT_TRUE(captured.str().empty());

    captured.str({});
    captured.clear();
    original = std::cout.rdbuf(captured.rdbuf());
    book.on_remove(OrderRemove{5, 999});
    std::cout.rdbuf(original);

    EXPECT_NE(captured.str().find("unknown order_id=999"), std::string::npos);
}

TEST(PortfolioTest, RiskAndPnl) {
    Portfolio portfolio(1'000.0, 3);

    const Order buy3{1, 1, Side::Bid, OrderType::Market, 0.0, 3, "test"};
    const Order buy4{2, 2, Side::Bid, OrderType::Market, 0.0, 4, "test"};
    EXPECT_TRUE(portfolio.pre_trade_check(buy3));
    EXPECT_FALSE(portfolio.pre_trade_check(buy4));

    portfolio.on_trade(Trade{1, 1, 10, 1, Side::Bid, 100.0, 3, "test"});
    EXPECT_EQ(portfolio.position(), 3);
    EXPECT_DOUBLE_EQ(portfolio.cash(), 700.0);

    portfolio.on_trade(Trade{2, 2, 11, 2, Side::Ask, 110.0, 1, "test"});
    EXPECT_EQ(portfolio.position(), 2);
    EXPECT_DOUBLE_EQ(portfolio.cash(), 810.0);
    EXPECT_DOUBLE_EQ(portfolio.realized_pnl(), 10.0);
    EXPECT_DOUBLE_EQ(portfolio.equity(100.0), 1'010.0);
}

TEST(RiskMetricsTest, ComputesSharpeDrawdownAndWinRate) {
    const std::vector<double> returns{0.01, -0.01, 0.02};
    EXPECT_NEAR(RiskMetrics::compute_sharpe(returns), 6.92820323027551, 1e-9);

    const std::vector<double> equity{100.0, 120.0, 90.0, 110.0, 80.0};
    EXPECT_NEAR(RiskMetrics::compute_max_drawdown(equity), 1.0 / 3.0, 1e-12);

    const std::vector<double> pnl_increments{1.0, -0.5, 0.0, 2.0};
    EXPECT_NEAR(RiskMetrics::compute_win_rate(pnl_increments), 2.0 / 3.0, 1e-12);
    EXPECT_DOUBLE_EQ(RiskMetrics::compute_avg_win(pnl_increments), 1.5);
    EXPECT_DOUBLE_EQ(RiskMetrics::compute_avg_loss(pnl_increments), -0.5);
}

TEST(StrategyFactoryTest, CreatesSupportedAliases) {
    EXPECT_EQ(make_strategy("momentum")->name(), "MomentumStrategy");
    EXPECT_EQ(make_strategy("mean_reversion")->name(), "MeanReversionStrategy");
    EXPECT_EQ(make_strategy("bollinger")->name(), "BollingerBandsStrategy");
    EXPECT_EQ(make_strategy("ma_cross")->name(), "MovingAverageCrossStrategy");

    EXPECT_EQ(make_strategy("meanreversion")->name(), "MeanReversionStrategy");
    EXPECT_EQ(make_strategy("mr")->name(), "MeanReversionStrategy");
    EXPECT_EQ(make_strategy("moving_average_cross")->name(), "MovingAverageCrossStrategy");

    EXPECT_THROW(static_cast<void>(make_strategy("unknown_strategy")), std::runtime_error);
}

TEST(StrategyEngineTest, ConvertsSignalIntoOrder) {
    StrategyEngine engine(std::make_unique<FixedSignalStrategy>(
        Signal::Buy,
        OrderType::Limit,
        3
    ));

    const MarketData data{42, 99.5, 100.5, 100.0, 10};
    const auto maybe_order = engine.maybe_create_order(data, data.timestamp);

    ASSERT_TRUE(maybe_order.has_value());
    EXPECT_EQ(maybe_order->order_id, 1000000u);
    EXPECT_EQ(maybe_order->timestamp, 42);
    EXPECT_EQ(maybe_order->side, Side::Bid);
    EXPECT_EQ(maybe_order->type, OrderType::Limit);
    EXPECT_DOUBLE_EQ(maybe_order->price, 100.5);
    EXPECT_EQ(maybe_order->quantity, 3);
    EXPECT_EQ(maybe_order->strategy_name, "FixedSignalStrategy");
}
