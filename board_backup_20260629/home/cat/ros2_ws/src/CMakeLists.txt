cmake_minimum_required(VERSION 3.16)
project(robot_reminder_bt)

if(CMAKE_CXX_STANDARD LESS 17)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(behaviortree_cpp_v3 REQUIRED)

add_library(reminder_bt_nodes SHARED
  src/reminder_nodes.cpp
)

target_include_directories(reminder_bt_nodes
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(reminder_bt_nodes
  rclcpp
  std_msgs
  behaviortree_cpp_v3
)

add_executable(reminder_bt_node
  src/reminder_bt_main.cpp
)

ament_target_dependencies(reminder_bt_node
  rclcpp
  std_msgs
  behaviortree_cpp_v3
)

target_link_libraries(reminder_bt_node
  reminder_bt_nodes
)

install(TARGETS
  reminder_bt_nodes
  reminder_bt_node
  RUNTIME DESTINATION lib/${PROJECT_NAME}
  LIBRARY DESTINATION lib
)

install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)
install(DIRECTORY launch/ DESTINATION share/${PROJECT_NAME}/launch)
install(FILES package.xml DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
