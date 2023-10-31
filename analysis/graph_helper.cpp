#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <sstream>
#include <iostream>
#include <omp.h>
#include <stdint.h>

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
                std::cerr << "Progress: " << results.size() << "/" << src_ips.size() << std::endl;
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

        std::priority_queue<std::tuple<int_fast8_t, unsigned int>, std::vector<std::tuple<int_fast8_t, unsigned int>>, std::greater<std::tuple<int_fast8_t, unsigned int>>> min_heap;
        std::unordered_map<unsigned int, int_fast8_t> distances;
        for (const auto &pair : graph) {
            distances[pair.first] = INT_FAST8_MAX;
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
                int_fast8_t distance = distances[current_node] + 1;
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
};

PYBIND11_MODULE(graph_module, m) {
    py::class_<Graph>(m, "Graph")
        .def(py::init<>())
        .def("add_edge", &Graph::add_edge)
        .def("parallelDijkstra", &Graph::parallelDijkstra);
}
