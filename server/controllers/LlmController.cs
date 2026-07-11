using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using System.ComponentModel.DataAnnotations;
using System.Net.Http;
using System.Text.Unicode;
using System.Text;

namespace LLM_MONITOR.server.controllers;


[ApiController]
[Route("/api/[controller]")]
public class LlmController: ControllerBase
{
    IHttpClientFactory _httpClientFactory;
    string? _langchainContainerUrl = Environment.GetEnvironmentVariable("OLLAMA_BASE_URL");
    public LlmController(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    // Ultimately I am going to need to service a POST request
    // The user will send me a POST request and in the request it will have the message which they want to send to the llm
    // We need to service that request by processing their request message and parsing the contents,
    // logging the telemetry data (actually I think the logging of telemetry data should not happen here it should be in the first middleware layer)


    // I was trying to come up with the variable which I expected would be the return type. I guessed it would have been something like IHttpResponse, but it was this thing I have never heard of IActionResult. What is this?
    [HttpPost]
    public async Task<IActionResult> LlmPostEndpoint([FromBody] IncomingRequestDto incomingRequestDto )
    {
        // set up POST request to send to LangChain docker container
        // I am realizing that I don't really know how or where the userId will come from. is it the user which will generate an id for themselves? Or do I create a GUID?
        LangchainRequstDto langchainRequstDto = new LangchainRequstDto
        {
            userId = "User Not Found",
            userRequestedModel = incomingRequestDto.UserRequestedModel,
            chatMessage = incomingRequestDto.UserMessage
        };

        string? stringifiedBody = JsonSerializer.Serialize(langchainRequstDto);

        var payload = new StringContent(stringifiedBody, Encoding.UTF8,"/application/json");

        var myClient = _httpClientFactory.CreateClient();

        HttpResponseMessage langchainResponse = await myClient.PostAsync($"{_langchainContainerUrl}/api/chat", payload);

        if (!langchainResponse.IsSuccessStatusCode)
        {
            return BadRequest("LLM gave not success response");
        }

        return Ok( new {success = true, responseMessage=langchainResponse});
    }

    // The way that I title my variables needs to match up with the http request which is coming in.
    // But C# has certain standards of variable naming, and other languages have other standards.
    // So how can I develop a system (or software) that will either give a contract to the caller, or be agnostic towards the system?
    // It seems this is so fragile.
    public class IncomingRequestDto
    {
        public string? UserMessage {get; set;}
        public string? UserRequestedModel {get; set;}
    }

    public class LangchainRequstDto
    {
        public string? userId {get; set;}
        public string? chatMessage {get; set;}
        public string? userRequestedModel {get; set;}
    }
}

// Commented-out LlmController_old draft moved to server/old_implementations/LlmController_old.cs
