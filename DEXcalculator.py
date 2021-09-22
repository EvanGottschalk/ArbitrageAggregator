from web3 import Web3
import json


class DEXcalculator:
    def __init__(self):
        self.connected = False
        self.web3_object = None
        self.ABI = json.loads('[{"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')
        self.contractAddresses = {'WETH': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', \
                                  'DAI': '0x6b175474e89094c44da98b954eedeac495271d0f'}
        self.exchangeAddresses = {'UniswapV2': '0xa478c2975ab1ea89e8196811f51a7b7ade33eb11', \
                                  'Sushiswap': '0xc3d03e4f041fd4cd388c549ee2a29a9e5075882f', \
                                  'Shebaswap': '0x8faf958e36c6970497386118030e6297fff8d275', \
                                  'Sakeswap': '0x2ad95483ac838e2884563ad278e933fba96bc242', \
                                  'Croswap': '0x60a26d69263ef43e9a68964ba141263f19d71d51'}


    def connectToWeb3(self, api_url=None):
        self.connected = False
        while not(self.connected):
            self.web3_object = Web3(Web3.HTTPProvider(api_url))
            if self.web3_object.isConnected():
                self.connected = True
                # security!
                del api_url
            else:
                if api_url:
                    print('\nConnection Error in EPC.connectToWeb3 : Invalid API URL. Double-check the API URL and try again.')
                api_url = input('\nPlease input your Alchemy.io API URL.\n\nAPI URL: ')
        return(self.web3_object)


    def fetchLatestBlockNumber(self):
        if not(self.connected):
            self.connectToWeb3()
        latest_block = self.web3_object.eth.get_block('latest')
        latest_block_number = latest_block['number']
        print('\nThe latest block number is ' + str(latest_block_number))
        return(latest_block_number)


    def fetchBalance(self, raw_wallet_address=None, raw_contract_address=None):
        valid_wallet_address = None
        valid_contract_address = None
        if not(self.connected):
            self.connectToWeb3()
            
        #1) The raw_wallet_address and raw_contract_address are converted using toChecksumAddress() and assigned to their "valid" counterparts
        while not(valid_wallet_address):
            try:
                valid_wallet_address = self.web3_object.toChecksumAddress(raw_wallet_address)
            except ValueError as error:
                if raw_wallet_address:
                    print('ValueError in EPC.fetchBalance : Invalid wallet address. Please double-check the wallet address and enter it again.')
                raw_wallet_address = input('\nPlease input the wallet address.\n\nWallet Address: ')
        while not(valid_contract_address):
            try:
                valid_contract_address = self.web3_object.toChecksumAddress(raw_contract_address)
            except ValueError as error:
                if raw_contract_address:
                    print('ValueError in EPC.fetchBalance : Invalid contract address. Please double-check the wallet address and enter it again.')
                raw_contract_address = input('\nPlease input the contract address.\n\nContract Address: ')
                
        #2) The wallet balance is fetched using the addresses provided
        contract_object = self.web3_object.eth.contract(valid_contract_address, abi=self.ABI)
        raw_balance = contract_object.functions.balanceOf(valid_wallet_address).call()
        
        #3) The amount in raw_balance is measured in Wei. It is converted to Ethereum for readability
        balance = float(self.web3_object.fromWei(raw_balance, 'ether'))
        return(balance)


    def fetchExchangeBalances(self, silent_mode=False):
        if not(self.connected):
            self.connectToWeb3()
        exchange_balances = {}
        if not(silent_mode):
            print('\nExchange Balances:')
        for exchange_name in self.exchangeAddresses:
            exchange_balances[exchange_name] = {}
            for token_name in self.contractAddresses:
                balance = self.fetchBalance(**{'raw_wallet_address': self.exchangeAddresses[exchange_name], \
                                               'raw_contract_address': self.contractAddresses[token_name]})
                exchange_balances[exchange_name][token_name] = balance
                if not(silent_mode):
                    print('    ' + exchange_name + ' ' + token_name + ' Balance: ' + str(balance))
        return(exchange_balances)


    def getPriceParameters(self, exchange_name=None, spent_token=None, received_token=None, spent_amount=None):
        exchange_address = None
        spent_token_address = None
        received_token_address = None
        
        # The addresses for the chosen exchange and tokens are retrieved so their respective balances can be fetched
        while not(exchange_address):
            exchange_address = self.exchangeAddresses.get(exchange_name)
            if not(exchange_address):
                if exchange_name:
                    print('ERROR! Invalid exchange name. Enter UniswapV2, Sushiswap, Shebaswap, Sakeswap, or Croswap.')
                exchange_name = input('\nPlease input the exchange that you would like to access.\n\nExchange Name: ')
                
        while not(spent_token_address):
            spent_token_address = self.contractAddresses.get(spent_token)
            if not(spent_token_address):
                if spent_token:
                    print('ERROR! Invalid token name. Enter WETH or DAI.')
                spent_token = input('\nPlease input the token that you would like to spend.\n\nSpent Token: ')
                
        while not(received_token_address):
            received_token_address = self.contractAddresses.get(received_token)
            if not(received_token_address):
                if received_token:
                    print('ERROR! Invalid token name. Enter WETH or DAI.')
                received_token = input('\nPlease input the token that you would to receive in exchange.\n\nReceived Token: ')
                
        while not(spent_amount) or spent_amount <= 0:
            if spent_amount:
                print('ERROR! Invalid amount. Please enter a real, positive number.')
            spent_amount = float(input('\nHow much ' + spent_token + ' would you like to spend on ' + received_token + '?\n\nAmount: '))
            
        spent_token_balance = self.fetchBalance(exchange_address, spent_token_address)
        received_token_balance = self.fetchBalance(exchange_address, received_token_address)
        return(spent_token_balance, received_token_balance, spent_amount, exchange_name, spent_token, received_token)

        
    def calculatePrice(self, spent_token_balance, received_token_balance, spent_amount, exchange_name=None, spent_token=None, received_token=None):
        price = None
        k = spent_token_balance * received_token_balance
        received_amount = round(received_token_balance - (k / (spent_token_balance + spent_amount)), 18)
        if received_amount > 0:
            price = spent_amount / received_amount
        if exchange_name and spent_token and received_token:
            print('\nSpending ' + str(spent_amount) + ' ' + spent_token + ' on ' + exchange_name + ' gets you ' + str(received_amount) + ' ' + \
                  received_token + ' at a price of ' + str(price) + ' ' + spent_token + ' per ' + received_token)
        return(price)
