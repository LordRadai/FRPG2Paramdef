#pragma once
#include <string>
#include <unordered_map>
#include <nlohmann/json.hpp>

namespace Paramdex
{
	class Enum
	{
		std::string m_name;
		std::string m_type;
		std::unordered_map<std::string, int> m_enumValues;

	public:
		Enum() : m_name(""), m_type("") {}
		Enum(const std::string& name, const std::string& type)
			: m_name(name), m_type(type)
		{
		}

		~Enum() {}

		const std::string& getName() const { return m_name; }
		const std::string& getType() const { return m_type; }
		const std::unordered_map<std::string, int>& getEnumValues() const { return m_enumValues; }

		void addValue(const std::string& name, int value) 
		{
			m_enumValues[name] = value;
		}

		void removeValue(const std::string& name) 
		{
			m_enumValues.erase(name);
		}

		void clearValues()
		{
			m_enumValues.clear();
		}

		bool hasValue(const std::string& name) const 
		{
			return m_enumValues.find(name) != m_enumValues.end();
		}

		bool loadFromTdf(const std::wstring& filePath);
		bool saveToTdf(const std::wstring& filePath) const;

		bool loadFromJson(const nlohmann::json& jsonData);
	};
}