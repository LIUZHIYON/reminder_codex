#ifndef ROBOT_REMINDER_BT_REMINDER_NODES_HPP
#define ROBOT_REMINDER_BT_REMINDER_NODES_HPP

/**
 * reminder_nodes.hpp — 行为树自定义节点（BT.CPP v3）
 *
 * 板子环境: ros-humble-behaviortree-cpp-v3 (3.8.7)
 * 编译: colcon build --packages-select robot_reminder_bt
 */

#include <behaviortree_cpp_v3/bt_factory.h>
#include <behaviortree_cpp_v3/action_node.h>
#include <behaviortree_cpp_v3/condition_node.h>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

using namespace BT;

// ═══════════════════════════════════════════════════════
//  Condition: 检查是否有待触发提醒
// ═══════════════════════════════════════════════════════

class CheckPendingReminder : public ConditionNode
{
public:
    CheckPendingReminder(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;

private:
    std::shared_ptr<rclcpp::Node> ros_node_;
};

// ═══════════════════════════════════════════════════════
//  Action: 获取提醒内容
// ═══════════════════════════════════════════════════════

class FetchReminder : public SyncActionNode
{
public:
    FetchReminder(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;
private:
    std::shared_ptr<rclcpp::Node> ros_node_;
};

// ═══════════════════════════════════════════════════════
//  Action: 合成语音（发布到 /tts/text）
// ═══════════════════════════════════════════════════════

class GenerateTTS : public SyncActionNode
{
public:
    GenerateTTS(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;

private:
    std::shared_ptr<rclcpp::Node> ros_node_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr tts_pub_;
};

// ═══════════════════════════════════════════════════════
//  Action: 播放音频（Stateful）
// ═══════════════════════════════════════════════════════

class PlayAudio : public StatefulActionNode
{
public:
    PlayAudio(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus onStart() override;
    NodeStatus onRunning() override;
    void onHalted() override;

private:
    std::shared_ptr<rclcpp::Node> ros_node_;
};

// ═══════════════════════════════════════════════════════
//  Action: WebSocket 通知
// ═══════════════════════════════════════════════════════

class NotifyWebSocket : public SyncActionNode
{
public:
    NotifyWebSocket(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;

private:
    std::shared_ptr<rclcpp::Node> ros_node_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr cmd_pub_;
};

// ═══════════════════════════════════════════════════════
//  Action: 标记已触发
// ═══════════════════════════════════════════════════════

class MarkTriggered : public SyncActionNode
{
public:
    MarkTriggered(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;
private:
    std::shared_ptr<rclcpp::Node> ros_node_;
};

// ═══════════════════════════════════════════════════════
//  Action: 记录日志
// ═══════════════════════════════════════════════════════

class LogReminder : public SyncActionNode
{
public:
    LogReminder(const std::string& name, const NodeConfiguration& config);
    static PortsList providedPorts();
    NodeStatus tick() override;
private:
    std::shared_ptr<rclcpp::Node> ros_node_;
};

// ═══════════════════════════════════════════════════════
//  注册所有节点
// ═══════════════════════════════════════════════════════

inline void RegisterReminderNodes(BT::BehaviorTreeFactory& factory)
{
    factory.registerNodeType<CheckPendingReminder>("CheckPendingReminder");
    factory.registerNodeType<FetchReminder>("FetchReminder");
    factory.registerNodeType<GenerateTTS>("GenerateTTS");
    factory.registerNodeType<PlayAudio>("PlayAudio");
    factory.registerNodeType<NotifyWebSocket>("NotifyWebSocket");
    factory.registerNodeType<MarkTriggered>("MarkTriggered");
    factory.registerNodeType<LogReminder>("LogReminder");
}

#endif // ROBOT_REMINDER_BT_REMINDER_NODES_HPP
