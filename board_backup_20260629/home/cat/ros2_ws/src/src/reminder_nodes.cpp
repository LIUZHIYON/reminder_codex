/**
 * reminder_nodes.cpp — 行为树自定义节点实现（BT.CPP v3 版）
 */

#include "robot_reminder_bt/reminder_nodes.hpp"
#include <fstream>
#include <cstdio>
#include <memory>
#include <array>

using namespace std::chrono_literals;

// ═══════════════════════════════════════════════════════
//  工具: 简易 HTTP GET
// ═══════════════════════════════════════════════════════

static std::string http_get(const std::string& url, int timeout_sec = 5)
{
    std::string cmd = "curl -s --connect-timeout " + std::to_string(timeout_sec)
                      + " --max-time " + std::to_string(timeout_sec) + " '" + url + "'";
    std::array<char, 4096> buffer;
    std::string result;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (pipe) {
        while (fgets(buffer.data(), buffer.size(), pipe) != nullptr)
            result += buffer.data();
        pclose(pipe);
    }
    return result;
}

static std::string http_post(const std::string& url, int timeout_sec = 5)
{
    std::string cmd = "curl -s -X POST --connect-timeout " + std::to_string(timeout_sec)
                      + " --max-time " + std::to_string(timeout_sec) + " '" + url + "'";
    std::array<char, 4096> buffer;
    std::string result;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (pipe) {
        while (fgets(buffer.data(), buffer.size(), pipe) != nullptr)
            result += buffer.data();
        pclose(pipe);
    }
    return result;
}

static std::string get_reminder_text(const std::string& json_str)
{
    // 简单 JSON 提取: 找 "content":"..."
    auto pos = json_str.find("\"content\"");
    if (pos == std::string::npos) return "";
    pos = json_str.find('"', pos + 10);
    if (pos == std::string::npos) return "";
    auto end = json_str.find('"', pos + 1);
    if (end == std::string::npos) return "";
    return json_str.substr(pos + 1, end - pos - 1);
}

static int get_reminder_id(const std::string& json_str)
{
    auto pos = json_str.find("\"id\"");
    if (pos == std::string::npos) return 0;
    auto colon = json_str.find(':', pos);
    if (colon == std::string::npos) return 0;
    auto end = json_str.find_first_of(",}", colon + 1);
    if (end == std::string::npos) return 0;
    try {
        return std::stoi(json_str.substr(colon + 1, end - colon - 1));
    } catch (...) {
        return 0;
    }
}

// ═══════════════════════════════════════════════════════
//  CheckPendingReminder
// ═══════════════════════════════════════════════════════

CheckPendingReminder::CheckPendingReminder(const std::string& name,
                                             const NodeConfiguration& config)
    : ConditionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_sub");
}

PortsList CheckPendingReminder::providedPorts()
{
    return {
        InputPort<std::string>("api_url", "http://192.168.1.70:5000"),
        OutputPort<std::string>("reminder_list")
    };
}

NodeStatus CheckPendingReminder::tick()
{
    std::string api_url = getInput<std::string>("api_url").value_or("http://192.168.1.70:5000");

    std::string stats = http_get(api_url + "/api/stats", 3);

    auto p = stats.find("\"pending\"");
    if (p == std::string::npos) return NodeStatus::FAILURE;

    auto c = stats.find(':', p);
    if (c == std::string::npos) return NodeStatus::FAILURE;

    auto e = stats.find_first_of(",}", c + 1);
    std::string num = stats.substr(c + 1, e - c - 1);

    try {
        if (std::stoi(num) > 0) {
            std::string list = http_get(api_url + "/api/reminders?status=pending", 3);
            setOutput("reminder_list", list);
            RCLCPP_INFO(ros_node_->get_logger(), "[BT] 发现待触发提醒");
            return NodeStatus::SUCCESS;
        }
    } catch (...) {}
    return NodeStatus::FAILURE;
}

// ═══════════════════════════════════════════════════════
//  FetchReminder
// ═══════════════════════════════════════════════════════

FetchReminder::FetchReminder(const std::string& name, const NodeConfiguration& config)
    : SyncActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_sub");
}

PortsList FetchReminder::providedPorts()
{
    return {
        InputPort<std::string>("reminder_list"),
        OutputPort<std::string>("current_reminder")
    };
}

NodeStatus FetchReminder::tick()
{
    auto list_opt = getInput<std::string>("reminder_list");
    if (!list_opt) return NodeStatus::FAILURE;

    const auto& json = list_opt.value();
    auto ds = json.find("\"data\":[");
    if (ds == std::string::npos) return NodeStatus::FAILURE;

    auto ob = json.find('{', ds);
    if (ob == std::string::npos) return NodeStatus::FAILURE;

    auto oe = json.find('}', ob);
    if (oe == std::string::npos) return NodeStatus::FAILURE;

    std::string first = json.substr(ob, oe - ob + 1);
    setOutput("current_reminder", first);

    RCLCPP_INFO(ros_node_->get_logger(), "[BT] 取到提醒: %s",
                get_reminder_text(first).c_str());
    return NodeStatus::SUCCESS;
}

// ═══════════════════════════════════════════════════════
//  GenerateTTS
// ═══════════════════════════════════════════════════════

GenerateTTS::GenerateTTS(const std::string& name, const NodeConfiguration& config)
    : SyncActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_node");
    tts_pub_ = ros_node_->create_publisher<std_msgs::msg::String>("/tts/text", 10);
}

PortsList GenerateTTS::providedPorts()
{
    return {
        InputPort<std::string>("reminder"),
        InputPort<std::string>("test_text")
    };
}

NodeStatus GenerateTTS::tick()
{
    std::string text;
    auto test_opt = getInput<std::string>("test_text");
    if (test_opt) {
        text = test_opt.value();
    } else {
        auto rem_opt = getInput<std::string>("reminder");
        text = get_reminder_text(rem_opt.value_or(""));
    }
    if (text.empty()) text = "您有一条新提醒";

    auto msg = std_msgs::msg::String();
    msg.data = text;
    tts_pub_->publish(msg);

    RCLCPP_INFO(ros_node_->get_logger(), "[BT] TTS: %s", text.c_str());
    return NodeStatus::SUCCESS;
}

// ═══════════════════════════════════════════════════════
//  PlayAudio
// ═══════════════════════════════════════════════════════

PlayAudio::PlayAudio(const std::string& name, const NodeConfiguration& config)
    : StatefulActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_node");
}

PortsList PlayAudio::providedPorts()
{
    return { InputPort<std::string>("reminder") };
}

NodeStatus PlayAudio::onStart()
{
    auto rem = getInput<std::string>("reminder");
    auto text = get_reminder_text(rem.value_or(""));
    RCLCPP_INFO(ros_node_->get_logger(), "[BT] 播放: %s", text.c_str());

    // TODO: 订阅 /audio/complete 做异步等待
    // 目前简单模拟播放耗时后直接完成
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    return NodeStatus::SUCCESS;
}

NodeStatus PlayAudio::onRunning()
{
    return NodeStatus::SUCCESS;
}

void PlayAudio::onHalted()
{
    RCLCPP_INFO(ros_node_->get_logger(), "[BT] 播放被中断");
}

// ═══════════════════════════════════════════════════════
//  NotifyWebSocket
// ═══════════════════════════════════════════════════════

NotifyWebSocket::NotifyWebSocket(const std::string& name, const NodeConfiguration& config)
    : SyncActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_node");
    cmd_pub_ = ros_node_->create_publisher<std_msgs::msg::String>("/robot/command", 10);
}

PortsList NotifyWebSocket::providedPorts()
{
    return { InputPort<std::string>("reminder") };
}

NodeStatus NotifyWebSocket::tick()
{
    auto rem = getInput<std::string>("reminder");
    auto text = get_reminder_text(rem.value_or(""));

    auto msg = std_msgs::msg::String();
    msg.data = R"({"type":"command_response","command":"reminder",)"
               R"("status":"success","result":{"played":true,"content":")"
               + text + R"("}})";
    cmd_pub_->publish(msg);

    RCLCPP_INFO(ros_node_->get_logger(), "[BT] WS通知: %s", text.c_str());
    return NodeStatus::SUCCESS;
}

// ═══════════════════════════════════════════════════════
//  MarkTriggered
// ═══════════════════════════════════════════════════════

MarkTriggered::MarkTriggered(const std::string& name, const NodeConfiguration& config)
    : SyncActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_sub");
}

PortsList MarkTriggered::providedPorts()
{
    return { InputPort<std::string>("reminder") };
}

NodeStatus MarkTriggered::tick()
{
    auto rem = getInput<std::string>("reminder");
    int rid = get_reminder_id(rem.value_or(""));
    if (rid == 0) return NodeStatus::FAILURE;

    std::string url = "http://192.168.1.70:5000/api/reminders/"
                      + std::to_string(rid) + "/trigger";
    http_post(url, 5);

    RCLCPP_INFO(ros_node_->get_logger(), "[BT] 标记 %d 已触发", rid);
    return NodeStatus::SUCCESS;
}

// ═══════════════════════════════════════════════════════
//  LogReminder
// ═══════════════════════════════════════════════════════

LogReminder::LogReminder(const std::string& name, const NodeConfiguration& config)
    : SyncActionNode(name, config)
{
    ros_node_ = std::make_shared<rclcpp::Node>(name + "_sub");
}

PortsList LogReminder::providedPorts()
{
    return { InputPort<std::string>("reminder") };
}

NodeStatus LogReminder::tick()
{
    auto rem = getInput<std::string>("reminder");
    auto text = get_reminder_text(rem.value_or(""));
    RCLCPP_INFO(ros_node_->get_logger(), "[BT] 日志: 播报完成 - %s", text.c_str());
    return NodeStatus::SUCCESS;
}
