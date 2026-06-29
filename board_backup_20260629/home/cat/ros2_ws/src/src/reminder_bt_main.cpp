/**
 * reminder_bt_main.cpp — ROS2 行为树节点 (BT.CPP v3)
 *
 * Groot2 调试: ZMQ Publisher 端口 1666
 *   Groot2 → Monitor → Connect → 192.168.1.70:1666 (ZMQ)
 *
 * 运行:
 *   ros2 run robot_reminder_bt reminder_bt_node --ros-args \
 *     -p api_url:=http://192.168.1.70:5000
 */

#include <rclcpp/rclcpp.hpp>
#include <fstream>
#include <behaviortree_cpp_v3/bt_factory.h>
#include <behaviortree_cpp_v3/loggers/bt_zmq_publisher.h>

#include "robot_reminder_bt/reminder_nodes.hpp"

class ReminderBTNode : public rclcpp::Node
{
public:
    ReminderBTNode()
        : Node("reminder_bt_node")
    {
        declare_parameter("api_url", "http://192.168.1.70:5000");
        declare_parameter("bt_xml", "");
        declare_parameter("tick_interval_ms", 100);
        declare_parameter("groot2_port", 1666);
        declare_parameter("groot2_enabled", true);

        api_url_ = get_parameter("api_url").as_string();
        std::string bt_xml = get_parameter("bt_xml").as_string();
        int tick_ms = get_parameter("tick_interval_ms").as_int();
        int g2_port = get_parameter("groot2_port").as_int();
        bool g2_enabled = get_parameter("groot2_enabled").as_bool();

        // 注册 BT 节点
        BT::BehaviorTreeFactory factory;
        RegisterReminderNodes(factory);

        // 加载 XML
        std::string xml_text;
        if (!bt_xml.empty()) {
            std::ifstream ifs(bt_xml);
            if (ifs.is_open()) {
                xml_text = std::string((std::istreambuf_iterator<char>(ifs)),
                                        std::istreambuf_iterator<char>());
                RCLCPP_INFO(get_logger(), "加载 XML: %s", bt_xml.c_str());
            } else {
                RCLCPP_WARN(get_logger(), "无法打开 XML: %s", bt_xml.c_str());
                xml_text = get_default_xml();
            }
        } else {
            xml_text = get_default_xml();
            RCLCPP_INFO(get_logger(), "使用内置 XML");
        }

        factory.registerBehaviorTreeFromText(xml_text);
        tree_ = factory.createTree("ReminderTree");

        // 黑板默认值
        tree_.rootBlackboard()->set("api_url", api_url_);

        // Groot2 ZMQ Publisher (v3 API)
        if (g2_enabled) {
            try {
                groot2_pub_ = std::make_shared<BT::PublisherZMQ>(
                    tree_, 25, (unsigned)g2_port, (unsigned)g2_port + 1);
                RCLCPP_INFO(get_logger(), "Groot2 ZMQ 已启动, 端口=%d", g2_port);
            } catch (const std::exception& e) {
                RCLCPP_WARN(get_logger(), "Groot2 启动失败: %s", e.what());
            }
        }

        // 定时器
        timer_ = create_wall_timer(
            std::chrono::milliseconds(tick_ms),
            std::bind(&ReminderBTNode::tick_bt, this));

        RCLCPP_INFO(get_logger(), "========= ReminderBTNode 启动 =========");
        RCLCPP_INFO(get_logger(), "  API: %s", api_url_.c_str());
        RCLCPP_INFO(get_logger(), "  Groot2: 192.168.1.70:%d (ZMQ)", g2_port);
        RCLCPP_INFO(get_logger(), "  Tick: %dms", tick_ms);
        RCLCPP_INFO(get_logger(), "========================================");
    }

private:
    void tick_bt()
    {
        BT::NodeStatus status = tree_.tickRoot();
        if (status == BT::NodeStatus::SUCCESS) {
            RCLCPP_DEBUG(get_logger(), "BT: SUCCESS");
        } else if (status == BT::NodeStatus::FAILURE) {
            RCLCPP_DEBUG(get_logger(), "BT: FAILURE");
        }
    }

    static std::string get_default_xml()
    {
        return R"(
<root BTCPP_format="4">
    <BehaviorTree ID="ReminderTree">
        <ReactiveSequence name="reminder_main_loop">
            <CheckPendingReminder
                name="has_pending_reminder"
                api_url="{api_url}"
                reminder_list="{pending_reminders}"/>
            <Sequence name="execute_reminder">
                <FetchReminder
                    name="fetch_reminder"
                    reminder_list="{pending_reminders}"
                    current_reminder="{current_reminder}"/>
                <RetryUntilSuccessful name="tts_retry" num_attempts="2">
                    <GenerateTTS reminder="{current_reminder}"/>
                </RetryUntilSuccessful>
                <RetryUntilSuccessful name="play_retry" num_attempts="2">
                    <PlayAudio reminder="{current_reminder}"/>
                </RetryUntilSuccessful>
                <RetryUntilSuccessful name="ws_retry" num_attempts="3">
                    <NotifyWebSocket reminder="{current_reminder}"/>
                </RetryUntilSuccessful>
                <MarkTriggered reminder="{current_reminder}"/>
                <LogReminder reminder="{current_reminder}"/>
            </Sequence>
        </ReactiveSequence>
    </BehaviorTree>
</root>
)";
    }

    std::string api_url_;
    BT::Tree tree_;
    rclcpp::TimerBase::SharedPtr timer_;
    std::shared_ptr<BT::PublisherZMQ> groot2_pub_;
};

int main(int argc, char* argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<ReminderBTNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
