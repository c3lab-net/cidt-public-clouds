#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <sstream>
#include <omp.h>

namespace py = pybind11;

class Graph {
public:
    std::unordered_map<unsigned int, std::unordered_set<unsigned int>> graph;

    std::vector<std::vector<unsigned int>> parallelDijkstra(const std::vector<unsigned int>& src_ips, const std::set<unsigned int>& destinations) {
        std::vector<std::vector<unsigned int>> results;

        #pragma omp parallel for
        for (unsigned long int i = 0; i < src_ips.size(); ++i) {
            auto result = dijkstra(src_ips[i], destinations);
            #pragma omp critical
            {
                results.emplace_back(std::move(result));
            }
        }
        return results;
    }
    
    void add_edge(const unsigned int &u, const unsigned int &v) {
        graph[u].insert(v);
        graph[v].insert(u);
    }

    std::vector<unsigned int> dijkstra(const unsigned int &start, const std::set<unsigned int> &destinations) {
        if (destinations.find(start) != destinations.end()) {
            return {start};
        }

        std::priority_queue<std::tuple<float, unsigned int>, std::vector<std::tuple<float, unsigned int>>, std::greater<std::tuple<float, unsigned int>>> min_heap;
        std::unordered_map<unsigned int, float> distances;
        for (const auto &pair : graph) {
            distances[pair.first] = std::numeric_limits<float>::infinity();
        }
        distances[start] = 0;
        std::unordered_map<unsigned int, unsigned int> prev;
        unsigned int current_node = start;

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

        std::vector<unsigned int> path;
        while (current_node != start) {
            path.push_back(current_node);
            current_node = prev[current_node];
        }
        path.push_back(start);
        std::reverse(path.begin(), path.end());
        return path;
    }

    unsigned int ipv4ToUInt(const std::string &ip) {
        std::vector<int> segments;
        std::stringstream ss(ip);
        std::string segment;
        
        while (std::getline(ss, segment, '.')) {
            segments.push_back(std::stoi(segment));
        }

        if (segments.size() != 4) {
            // Invalid IPv4 address
            return 0;
        }

        unsigned int result = 0;
        for (int i = 0; i < 4; ++i) {
            result = (result << 8) | (segments[i] & 0xFF);
        }

        return result;
    }
    std::string uintToIPv4(unsigned int ipInt) {
    std::string ip = "";
    for (int i = 0; i < 4; ++i) {
        if (i != 0) {
            ip = "." + ip;
        }
        ip = std::to_string(ipInt & 0xFF) + ip;
        ipInt >>= 8;
    }
    return ip;
}
};

PYBIND11_MODULE(graph_module, m) {
    py::class_<Graph>(m, "Graph")
        .def(py::init<>())
        .def("add_edge", &Graph::add_edge)
        .def("dijkstra", &Graph::dijkstra)
        .def("ipv4ToUInt", &Graph::ipv4ToUInt)
        .def("uintToIPv4", &Graph::uintToIPv4)
        .def("parallelDijkstra", &Graph::parallelDijkstra);
}
