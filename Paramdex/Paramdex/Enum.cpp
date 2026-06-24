#include <fstream>
#include <sstream>
#include <iomanip>

#include "Enum.h"

namespace
{
    std::string StripQuotes(const std::string& str)
    {
        if (str.size() >= 2 && str.front() == L'\"' && str.back() == L'\"')
            return str.substr(1, str.size() - 2);

        return str;
    }
}

namespace Paramdex
{
    bool Enum::loadFromTdf(const std::wstring& filePath) 
    {
        std::ifstream file(filePath);

        if (!file.is_open())
        {
			throw std::runtime_error("Failed to open file: " + std::string(filePath.begin(), filePath.end()));
			return false;
        }

        std::string line;

        // 1. Load Name (Line 1)
        if (std::getline(file, line))
            m_name = StripQuotes(line);
        else return false;

        // 2. Load Type (Line 2)
        if (std::getline(file, line))
            m_type = StripQuotes(line);
        else return false;

        m_enumValues.clear();
        while (std::getline(file, line)) 
        {
            if (line.empty()) continue;

            std::stringstream ss(line);
            std::string key, valueStr;

            // TDF uses "Key","Value" format
            if (std::getline(ss, key, ',') && std::getline(ss, valueStr)) {
                std::string cleanKey = StripQuotes(key);
                std::string cleanVal = StripQuotes(valueStr);

                try 
                {
                    int val = std::stoi(cleanVal);
                    m_enumValues[cleanKey] = std::stoi(cleanVal);
                }
                catch (...) 
                {
					fprintf(stderr, "Warning: Invalid enum value '%s' for key '%s' in file '%s'. Skipping.\n", cleanVal.c_str(), cleanKey.c_str(), filePath.c_str());
                    continue;
                }
            }
        }

        return true;
    }

    bool Enum::saveToTdf(const std::wstring& filePath) const 
    {
        std::ofstream file(filePath);
        if (!file.is_open()) return false;

        file << "\"" << m_name << "\"\n";
        file << "\"" << m_type << "\"\n";

        for (const auto& pair : m_enumValues)
            file << "\"" << pair.first << "\",\"" << pair.second << "\"\n";

        return true;
    }

    bool Enum::loadFromJson(const nlohmann::json& jsonData) 
    {
        if (!jsonData.contains("Name") || !jsonData["Name"].is_string())
            return false;

        m_name = jsonData["Name"].get<std::string>();
        m_type = "";

        if (jsonData.contains("Type"))
            m_type = jsonData["Type"].get<std::string>();

        m_enumValues.clear();
        if (jsonData.contains("Options") && jsonData["Options"].is_array()) 
        {
            for (const auto& option : jsonData["Options"])
            {
                std::string id = option["ID"];
                std::string name = option["Name"];

                int value = std::stoi(id);
                m_enumValues[name] = value;
            }
        }

        return true;
	}
}
