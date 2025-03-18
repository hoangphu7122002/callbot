package src

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	
)

type DifyBotClient struct {
	apiURL         string
	apiKey         string
	headers        map[string]string
	conversationID string
}

type DifyRequest struct {
	Inputs         map[string]interface{} `json:"inputs"`
	Query          string                 `json:"query"`
	ResponseMode   string                 `json:"response_mode"`
	ConversationID string                 `json:"conversation_id"`
	User           string                 `json:"user"`
	Files          []interface{}          `json:"files"`
}

type DifyResponse struct {
	Answer         string `json:"answer"`
	ConversationID string `json:"conversation_id"`
}

func NewDifyBotClient(apiURL, apiKey string) *DifyBotClient {
	return &DifyBotClient{
		apiURL: apiURL,
		apiKey: apiKey,
		headers: map[string]string{
			"Authorization": fmt.Sprintf("Bearer %s", apiKey),
			"Content-Type":  "application/json",
		},
	}
}

// func NewDifyBotClient() *DifyBotClient {
// 	// cfg := config.GetConfig()
// 	return &DifyBotClient{
// 		apiURL: cfg.DifyAPIURL,
// 		apiKey: cfg.DifyAPIKey,
// 		headers: map[string]string{
// 			"Authorization": fmt.Sprintf("Bearer %s", cfg.DifyAPIKey),
// 			"Content-Type":  "application/json",
// 		},
// 	}
// }

func (d *DifyBotClient) GetResponse(query string, userID string) (string, error) {
	if userID == "" {
		userID = "default-user"
	}

	payload := DifyRequest{
		Inputs:       map[string]interface{}{},
		Query:        query,
		ResponseMode: "blocking",
		User:         userID,
		Files:        []interface{}{},
	}

	if d.conversationID != "" {
		payload.ConversationID = d.conversationID
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("error marshaling request: %v", err)
	}

	req, err := http.NewRequest("POST", d.apiURL, bytes.NewBuffer(jsonPayload))
	if err != nil {
		return "", fmt.Errorf("error creating request: %v", err)
	}

	for key, value := range d.headers {
		req.Header.Set(key, value)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("error calling Dify API: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("API returned non-200 status code: %d, body: %s", resp.StatusCode, string(body))
	}

	var response DifyResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return "", fmt.Errorf("error decoding response: %v", err)
	}

	if response.ConversationID != "" {
		d.conversationID = response.ConversationID
	}

	return response.Answer, nil
}

func (d *DifyBotClient) EndConversation(userID string) error {
	if d.conversationID == "" {
		return nil
	}

	if userID == "" {
		userID = "default-user"
	}

	baseURL := strings.TrimSuffix(d.apiURL, "/chat-messages")
	url := fmt.Sprintf("%s/conversations/%s", baseURL, d.conversationID)

	payload := map[string]string{
		"user": userID,
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("error marshaling request: %v", err)
	}

	req, err := http.NewRequest("DELETE", url, bytes.NewBuffer(jsonPayload))
	if err != nil {
		return fmt.Errorf("error creating request: %v", err)
	}

	for key, value := range d.headers {
		req.Header.Set(key, value)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error ending conversation: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API returned non-200 status code: %d, body: %s", resp.StatusCode, string(body))
	}

	d.conversationID = ""
	return nil
}

func (d *DifyBotClient) ResetConversation() {
	d.conversationID = ""
}
