package src

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
)

type LocalBotClient struct {
	ApiUrl         string
	ConversationId int
}

type RequestBody struct {
	ConversationId int    `json:"conversation_id"`
	Content        string `json:"content"`
	Collection     string `json:"collection"`
}

type ResponseBody struct {
	BotResponse string `json:"bot_response"`
}

func NewLocalBotClient(apiUrl string) *LocalBotClient {
	return &LocalBotClient{
		ApiUrl:         apiUrl,
		ConversationId: 0,
	}
}

func (c *LocalBotClient) GetResponse(message string) (string, error) {
	reqBody := RequestBody{
		ConversationId: c.ConversationId,
		Content:        message,
		Collection:     "general",
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		log.Printf("Error marshaling request: %v", err)
		return "Xin lỗi, tôi đang gặp sự cố kỹ thuật.", err
	}

	resp, err := http.Post(c.ApiUrl, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("Error calling local LLM API: %v", err)
		return "Xin lỗi, tôi đang gặp sự cố kỹ thuật.", err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Error reading response body: %v", err)
			return "Xin lỗi, tôi đang gặp sự cố kỹ thuật.", err
		}

		var response ResponseBody
		if err := json.Unmarshal(body, &response); err != nil {
			log.Printf("Error unmarshaling response: %v", err)
			return "Xin lỗi, tôi đang gặp sự cố kỹ thuật.", err
		}

		return response.BotResponse, nil
	}

	log.Printf("Error from local LLM API: %d", resp.StatusCode)
	return "Xin lỗi, tôi đang gặp sự cố kỹ thuật.", fmt.Errorf("API returned status code %d", resp.StatusCode)
}

func (c *LocalBotClient) EndConversation() {
	c.ConversationId = 0
}
