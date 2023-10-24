#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <queue>
#include <set>
#include <string>
#include <tuple>

namespace py = pybind11;

class Graph {
public:
    std::unordered_map<std::string, std::set<std::string>> graph;

    void add_edge(const std::string &u, const std::string &v) {
        graph[u].insert(v);
        graph[v].insert(u);
    }

    std::vector<std::string> dijkstra(const std::string &start, const std::set<std::string> &destinations) {
        if (destinations.find(start) != destinations.end()) {
            return {start};
        }

        std::priority_queue<std::tuple<float, std::string>, std::vector<std::tuple<float, std::string>>, std::greater<std::tuple<float, std::string>>> min_heap;
        std::unordered_map<std::string, float> distances;
        for (const auto &pair : graph) {
            distances[pair.first] = std::numeric_limits<float>::infinity();
        }
        distances[start] = 0;
        std::unordered_map<std::string, std::string> prev;
        std::string current_node = start;

        min_heap.push(std::make_tuple(0, start));

        while (!min_heap.empty()) {
            std::tie(std::ignore, current_node) = min_heap.top();
            min_heap.pop();

            if (destinations.find(current_node) != destinations.end()) {
                break;
            }

            for (const auto &neighbor : graph[current_node]) {
                float distance = distances[current_node] + 1;
                if (distance < distances[neighbor]) {
                    distances[neighbor] = distance;
                    min_heap.push(std::make_tuple(distance, neighbor));
                    prev[neighbor] = current_node;
                }
            }
        }

        if (prev.find(current_node) == prev.end()) {
            return {};
        }

        std::vector<std::string> path;
        while (current_node != start) {
            path.push_back(current_node);
            current_node = prev[current_node];
        }
        path.push_back(start);
        std::reverse(path.begin(), path.end());
        return path;
    }
};

PYBIND11_MODULE(graph_module, m) {
    py::class_<Graph>(m, "Graph")
        .def(py::init<>())
        .def("add_edge", &Graph::add_edge)
        .def("dijkstra", &Graph::dijkstra);
}
