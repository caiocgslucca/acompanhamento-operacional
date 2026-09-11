# Acesso online gratuito sem cartão

Esta opção usa Cloudflare Quick Tunnel. Ela não exige cartão, conta Cloudflare
ou abertura da porta 8000 no firewall. O endereço usa HTTPS e pode ser aberto
em celular ou notebook conectado a qualquer rede.

## Como iniciar

1. Extraia o ZIP em uma pasta local, por exemplo `C:\Projetos\Operacional`.
2. Feche qualquer execução antiga do aplicativo ou da porta 8000.
3. Execute `INICIAR_ONLINE_GRATIS.bat`.
4. Na primeira execução, aguarde a instalação das bibliotecas e o download do
   arquivo oficial `cloudflared.exe`.
5. Informe um usuário e crie uma senha com pelo menos 8 caracteres.
6. Aguarde aparecer o endereço `https://...trycloudflare.com/carteira`.
7. Compartilhe o endereço, usuário e senha somente com pessoas autorizadas.

O endereço também será gravado em `ENDERECO_ONLINE.txt`.

## Regras importantes

- Mantenha a janela aberta e o computador ligado.
- O endereço muda sempre que o iniciador for fechado e aberto novamente.
- As fontes continuam sendo as pastas cadastradas no computador.
- A atualização automática continua funcionando normalmente.
- Para encerrar, pressione `CTRL+C`.
- Caso `cloudflared.exe` seja bloqueado, solicite à TI a liberação desse nome
  exato. O sistema não desativa nem contorna o antivírus corporativo.

Quick Tunnel é indicado para operação controlada e poucos usuários. Para um
endereço permanente será necessário usar um domínio em uma conta Cloudflare ou
uma hospedagem corporativa aprovada.
